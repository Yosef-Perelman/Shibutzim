import { describe, expect, it, vi } from 'vitest';

import { ApiError } from '../api/apiClient';
import type { Assignment, Schedule, ShiftCoverage } from '../api/types/schedule';
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
  const api = { schedules: { get: vi.fn() } };
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
