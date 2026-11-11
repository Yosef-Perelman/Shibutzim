import { describe, expect, it, vi } from 'vitest';

import { ApiError } from '../api/apiClient';
import type { Shift } from '../api/types/shift';
import type {
  Assignment,
  AssignmentEditOut,
  Schedule,
  ScheduleGenerateOut,
  ShiftCoverage,
} from '../api/types/schedule';
import { ScheduleStore } from './ScheduleStore';

const WEEK = '2026-11-15';

function coverage(id: number, name: string, startsAt: string, endsAt: string): ShiftCoverage {
  return {
    shift_id: id,
    name,
    starts_at: startsAt,
    ends_at: endsAt,
    required_staff: 2,
    assigned_count: 2,
    unfilled_count: 0,
  };
}

function assignment(id: number, shiftId: number, userId: number, name: string): Assignment {
  return {
    id,
    shift_id: shiftId,
    user_id: userId,
    user_name: name,
    starts_at: '',
    ends_at: '',
  };
}

// Sun 15 Nov morning, Sun evening, Mon morning (Jerusalem times 07:00, 16:00, 07:00).
const SHIFTS = [
  coverage(2, 'Evening', '2026-11-15T14:00:00Z', '2026-11-15T21:00:00Z'),
  coverage(1, 'Morning', '2026-11-15T05:00:00Z', '2026-11-15T13:00:00Z'),
  coverage(3, 'Morning', '2026-11-16T05:00:00Z', '2026-11-16T13:00:00Z'),
];

function makeSchedule(overrides: Partial<Schedule> = {}): Schedule {
  return {
    id: 10,
    week_start: WEEK,
    status: 'published',
    published_at: '2026-11-10T08:00:00Z',
    shifts: SHIFTS,
    assignments: [
      assignment(1, 1, 7, 'Omer Barak'),
      assignment(2, 1, 1, 'Noa Katz'),
      assignment(3, 2, 7, 'Omer Barak'),
      assignment(4, 3, 1, 'Noa Katz'),
      assignment(5, 3, 7, 'Omer Barak'),
    ],
    ...overrides,
  };
}

function setup(currentUserId: number | null = 1) {
  const api = {
    schedules: {
      get: vi.fn(),
      generate: vi.fn(),
      publish: vi.fn(),
      addAssignment: vi.fn(),
      replaceAssignment: vi.fn(),
      removeAssignment: vi.fn(),
    },
    shifts: { list: vi.fn().mockResolvedValue([]), generate: vi.fn() },
    users: { list: vi.fn() },
  };
  const store = new ScheduleStore({ api, currentUserId: () => currentUserId });
  return { api, store };
}

describe('ScheduleStore.loadWeek', () => {
  it('loads the published schedule of a week', async () => {
    const { api, store } = setup();
    api.schedules.get.mockResolvedValue(makeSchedule());
    await store.loadWeek(WEEK);
    expect(api.schedules.get).toHaveBeenCalledWith(WEEK);
    expect(store.weekStart).toBe(WEEK);
    expect(store.status).toBe('loaded');
    expect(store.hasSchedule).toBe(true);
  });

  it('is loading while the request runs', async () => {
    const { api, store } = setup();
    let finish: (value: Schedule) => void = () => undefined;
    api.schedules.get.mockReturnValue(new Promise((resolve) => (finish = resolve)));
    const pending = store.loadWeek(WEEK);
    expect(store.status).toBe('loading');
    finish(makeSchedule());
    await pending;
    expect(store.status).toBe('loaded');
  });

  it('treats schedule_not_found as an empty week, not as an error', async () => {
    const { api, store } = setup();
    api.schedules.get.mockRejectedValue(
      new ApiError(404, 'schedule_not_found', 'There is no schedule for the week of 2026-11-15.'),
    );
    await store.loadWeek(WEEK);
    expect(store.status).toBe('loaded');
    expect(store.hasSchedule).toBe(false);
    expect(store.error).toBeNull();
  });

  it('keeps the server message for any other failure and can retry', async () => {
    const { api, store } = setup();
    api.schedules.get.mockRejectedValueOnce(
      new ApiError(0, 'network_error', 'Could not reach the server.'),
    );
    await store.loadWeek(WEEK);
    expect(store.status).toBe('error');
    expect(store.error).toBe('Could not reach the server.');
    api.schedules.get.mockResolvedValueOnce(makeSchedule());
    await store.reload();
    expect(store.status).toBe('loaded');
    expect(store.error).toBeNull();
  });

  it('clears the previous week when a new week has no schedule', async () => {
    const { api, store } = setup();
    api.schedules.get.mockResolvedValueOnce(makeSchedule());
    await store.loadWeek(WEEK);
    api.schedules.get.mockRejectedValueOnce(new ApiError(404, 'schedule_not_found', 'None.'));
    await store.loadWeek('2026-11-22');
    expect(store.hasSchedule).toBe(false);
  });

  it('ignores a slow answer for a week the user already left', async () => {
    const { api, store } = setup();
    let finishOld: (value: Schedule) => void = () => undefined;
    api.schedules.get.mockReturnValueOnce(new Promise((resolve) => (finishOld = resolve)));
    const old = store.loadWeek(WEEK);
    api.schedules.get.mockResolvedValueOnce(makeSchedule({ week_start: '2026-11-22', id: 11 }));
    await store.loadWeek('2026-11-22');
    finishOld(makeSchedule());
    await old;
    expect(store.weekStart).toBe('2026-11-22');
    expect(store.schedule?.id).toBe(11);
  });
});

describe('ScheduleStore.goToWeek', () => {
  it('moves to the next and the previous week and loads it', async () => {
    const { api, store } = setup();
    api.schedules.get.mockResolvedValue(makeSchedule());
    await store.loadWeek(WEEK);
    await store.goToWeek(1);
    expect(api.schedules.get).toHaveBeenLastCalledWith('2026-11-22');
    await store.goToWeek(-2);
    expect(api.schedules.get).toHaveBeenLastCalledWith('2026-11-08');
  });
});

describe('ScheduleStore own assignments first', () => {
  it("lists only the current user's assignments, earliest shift first", async () => {
    const { api, store } = setup(1);
    api.schedules.get.mockResolvedValue(makeSchedule());
    await store.loadWeek(WEEK);
    expect(store.mine.map((item) => item.shift.shift_id)).toEqual([1, 3]);
    expect(store.mine.every((item) => item.isMine)).toBe(true);
  });

  it('is empty for someone with no shifts that week', async () => {
    const { api, store } = setup(99);
    api.schedules.get.mockResolvedValue(makeSchedule());
    await store.loadWeek(WEEK);
    expect(store.mine).toEqual([]);
  });

  it('groups the whole team by local day, earliest shift first, own name marked', async () => {
    const { api, store } = setup(1);
    api.schedules.get.mockResolvedValue(makeSchedule());
    await store.loadWeek(WEEK);
    expect(store.days.map((day) => day.date)).toEqual(['2026-11-15', '2026-11-16']);
    const sunday = store.days[0];
    expect(sunday?.shifts.map((item) => item.shift.name)).toEqual(['Morning', 'Evening']);
    expect(sunday?.shifts[0]?.people.map((person) => person.user_name)).toEqual([
      'Noa Katz',
      'Omer Barak',
    ]);
    expect(sunday?.shifts[0]?.isMine).toBe(true);
    expect(sunday?.shifts[1]?.isMine).toBe(false);
  });

  it('puts the current user first among the people of a shift', async () => {
    const { api, store } = setup(1);
    api.schedules.get.mockResolvedValue(makeSchedule());
    await store.loadWeek(WEEK);
    expect(store.days[0]?.shifts[0]?.people[0]?.user_id).toBe(1);
  });
});

// --- the manager's board ---

function shiftDto(id: number, name: string, startsAt: string, endsAt: string): Shift {
  return {
    id,
    template_id: id,
    name,
    week_start: WEEK,
    starts_at: startsAt,
    ends_at: endsAt,
    required_staff: 2,
  };
}

const WEEK_SHIFTS = [
  shiftDto(1, 'Morning', '2026-11-15T05:00:00Z', '2026-11-15T13:00:00Z'),
  shiftDto(2, 'Evening', '2026-11-15T14:00:00Z', '2026-11-15T21:00:00Z'),
];

function edit(userId: number, warnings: AssignmentEditOut['warnings'] = []): AssignmentEditOut {
  return { assignment: assignment(9, 1, userId, 'Dana Other'), warnings };
}

function generated(overrides: Partial<ScheduleGenerateOut> = {}): ScheduleGenerateOut {
  return {
    schedule: makeSchedule({ status: 'draft', published_at: null }),
    unfilled: [
      {
        shift_id: 2,
        required: 2,
        assigned: 1,
        missing: 1,
        reasons: [],
        sentence: 'Sunday 16:00 needs 2, only 1 available',
      },
    ],
    score: { filled: 4, preferred: 1, spread_minutes: 60, value: 60 },
    complete: true,
    steps: 12,
    ...overrides,
  };
}

function notFound() {
  return new ApiError(404, 'schedule_not_found', 'None.');
}

describe('ScheduleStore.loadBoard', () => {
  it('shows the shifts of a week that has no schedule yet, with nobody assigned', async () => {
    const { api, store } = setup();
    api.shifts.list.mockResolvedValue(WEEK_SHIFTS);
    api.schedules.get.mockRejectedValue(notFound());
    await store.loadBoard(WEEK);
    expect(api.shifts.list).toHaveBeenCalledWith(WEEK);
    expect(store.status).toBe('loaded');
    expect(store.hasShifts).toBe(true);
    expect(store.scheduleStatus).toBeNull();
    expect(store.entries.map((entry) => [entry.shift.name, entry.shift.assigned_count])).toEqual([
      ['Morning', 0],
      ['Evening', 0],
    ]);
  });

  it('knows a week with no shifts at all', async () => {
    const { api, store } = setup();
    api.shifts.list.mockResolvedValue([]);
    api.schedules.get.mockRejectedValue(notFound());
    await store.loadBoard(WEEK);
    expect(store.hasShifts).toBe(false);
  });

  it("uses the schedule's coverage once there is one", async () => {
    const { api, store } = setup();
    api.shifts.list.mockResolvedValue(WEEK_SHIFTS);
    api.schedules.get.mockResolvedValue(makeSchedule({ status: 'draft' }));
    await store.loadBoard(WEEK);
    expect(store.scheduleStatus).toBe('draft');
    expect(store.entries[0]?.people.length).toBe(2);
  });

  it('keeps loading the shifts when the manager changes week', async () => {
    const { api, store } = setup();
    api.schedules.get.mockRejectedValue(notFound());
    await store.loadBoard(WEEK);
    api.shifts.list.mockClear();
    await store.goToWeek(1);
    expect(api.shifts.list).toHaveBeenCalledWith('2026-11-22');
  });

  it('forgets the last generate result when the week changes', async () => {
    const { api, store } = setup();
    api.shifts.list.mockResolvedValue(WEEK_SHIFTS);
    api.schedules.get.mockRejectedValue(notFound());
    await store.loadBoard(WEEK);
    api.schedules.generate.mockResolvedValue(generated());
    await store.generate();
    expect(store.lastRun).not.toBeNull();
    await store.goToWeek(1);
    expect(store.lastRun).toBeNull();
  });
});

describe('ScheduleStore.createShifts', () => {
  it("creates the week's shifts and reloads the board", async () => {
    const { api, store } = setup();
    api.shifts.list.mockResolvedValueOnce([]);
    api.schedules.get.mockRejectedValue(notFound());
    await store.loadBoard(WEEK);
    api.shifts.generate.mockResolvedValue({ week_start: WEEK, created: 2, shifts: WEEK_SHIFTS });
    api.shifts.list.mockResolvedValue(WEEK_SHIFTS);
    const result = await store.createShifts();
    expect(api.shifts.generate).toHaveBeenCalledWith(WEEK);
    expect(result).toEqual({ ok: true, warnings: [] });
    expect(store.hasShifts).toBe(true);
  });

  it('reports the server message when it fails', async () => {
    const { api, store } = setup();
    api.shifts.generate.mockRejectedValue(new ApiError(403, 'forbidden', 'Managers only.'));
    expect(await store.createShifts()).toEqual({
      ok: false,
      code: 'forbidden',
      message: 'Managers only.',
    });
  });
});

describe('ScheduleStore.generate', () => {
  it('stores the draft and keeps what the solver reported', async () => {
    const { api, store } = setup();
    api.schedules.generate.mockResolvedValue(generated());
    const result = await store.generate();
    expect(api.schedules.generate).toHaveBeenCalledWith(store.weekStart);
    expect(result.ok).toBe(true);
    expect(store.scheduleStatus).toBe('draft');
    expect(store.lastRun?.unfilled[0]?.sentence).toBe('Sunday 16:00 needs 2, only 1 available');
    expect(store.lastRun?.complete).toBe(true);
  });

  it('is working while the solver runs', async () => {
    const { api, store } = setup();
    let finish: (value: ScheduleGenerateOut) => void = () => undefined;
    api.schedules.generate.mockReturnValue(new Promise((resolve) => (finish = resolve)));
    const pending = store.generate();
    expect(store.isWorking).toBe(true);
    finish(generated());
    await pending;
    expect(store.isWorking).toBe(false);
  });

  it('keeps the current schedule and returns the server message when generate is refused', async () => {
    const { api, store } = setup();
    api.schedules.get.mockResolvedValue(makeSchedule());
    await store.loadWeek(WEEK);
    api.schedules.generate.mockRejectedValue(
      new ApiError(409, 'schedule_published', 'This schedule is already published.'),
    );
    const result = await store.generate();
    expect(result).toEqual({
      ok: false,
      code: 'schedule_published',
      message: 'This schedule is already published.',
    });
    expect(store.scheduleStatus).toBe('published');
  });

  it('cannot generate once the schedule is published', async () => {
    const { api, store } = setup();
    api.schedules.get.mockResolvedValue(makeSchedule({ status: 'published' }));
    await store.loadWeek(WEEK);
    expect(store.canGenerate).toBe(false);
  });
});

describe('ScheduleStore.publish', () => {
  it('marks the schedule published', async () => {
    const { api, store } = setup();
    api.schedules.get.mockResolvedValue(makeSchedule({ status: 'draft', published_at: null }));
    await store.loadWeek(WEEK);
    api.schedules.publish.mockResolvedValue(makeSchedule({ status: 'published' }));
    const result = await store.publish();
    expect(api.schedules.publish).toHaveBeenCalledWith(WEEK);
    expect(result.ok).toBe(true);
    expect(store.scheduleStatus).toBe('published');
  });
});

describe('ScheduleStore assignment edits', () => {
  async function loadedDraft() {
    const ctx = setup();
    ctx.api.shifts.list.mockResolvedValue(WEEK_SHIFTS);
    ctx.api.schedules.get.mockResolvedValue(makeSchedule({ status: 'draft' }));
    await ctx.store.loadBoard(WEEK);
    ctx.api.schedules.get.mockClear();
    return ctx;
  }

  it('adds an assignment, passes the warnings on and refreshes the schedule without a loading flash', async () => {
    const { api, store } = await loadedDraft();
    const warning = {
      code: 'availability_ignored',
      message: 'Dana did not offer to work this shift.',
    };
    api.schedules.addAssignment.mockResolvedValue(edit(3, [warning]));
    const result = await store.addAssignment(1, 3);
    expect(api.schedules.addAssignment).toHaveBeenCalledWith(WEEK, { shift_id: 1, user_id: 3 });
    expect(result).toEqual({ ok: true, warnings: [warning] });
    expect(api.schedules.get).toHaveBeenCalledTimes(1);
    expect(store.status).toBe('loaded');
  });

  it('returns a blocking error as a result and leaves the schedule alone', async () => {
    const { api, store } = await loadedDraft();
    api.schedules.addAssignment.mockRejectedValue(
      new ApiError(409, 'min_rest_violation', 'Dana needs 8 hours of rest.'),
    );
    const result = await store.addAssignment(1, 3);
    expect(result).toEqual({
      ok: false,
      code: 'min_rest_violation',
      message: 'Dana needs 8 hours of rest.',
    });
    expect(api.schedules.get).not.toHaveBeenCalled();
  });

  it('replaces an assignment', async () => {
    const { api, store } = await loadedDraft();
    api.schedules.replaceAssignment.mockResolvedValue(edit(3));
    const result = await store.replaceAssignment(4, 3);
    expect(api.schedules.replaceAssignment).toHaveBeenCalledWith(WEEK, 4, { user_id: 3 });
    expect(result.ok).toBe(true);
    expect(api.schedules.get).toHaveBeenCalledTimes(1);
  });

  it('removes an assignment', async () => {
    const { api, store } = await loadedDraft();
    api.schedules.removeAssignment.mockResolvedValue(undefined);
    const result = await store.removeAssignment(4);
    expect(api.schedules.removeAssignment).toHaveBeenCalledWith(WEEK, 4);
    expect(result).toEqual({ ok: true, warnings: [] });
    expect(api.schedules.get).toHaveBeenCalledTimes(1);
  });
});

describe('ScheduleStore.loadEmployees', () => {
  it('loads the active employees for the picker', async () => {
    const { api, store } = setup();
    api.users.list.mockResolvedValue([
      {
        id: 1,
        email: 'noa@x',
        name: 'Noa Katz',
        role: 'employee',
        hourly_rate: '40.00',
        is_active: true,
      },
    ]);
    await store.loadEmployees();
    expect(api.users.list).toHaveBeenCalledWith({ role: 'employee', is_active: true });
    expect(store.employees.map((user) => user.name)).toEqual(['Noa Katz']);
  });
});
