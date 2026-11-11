import { describe, expect, it, vi } from 'vitest';

import { ApiError } from '../api/apiClient';
import type { Availability } from '../api/types/availability';
import type { Shift } from '../api/types/shift';
import { AvailabilityStore } from './AvailabilityStore';

// "Now" is Monday 9 Nov 2026 (week of Sunday 8 Nov); the form opens on next week.
const NOW = new Date('2026-11-09T12:00:00Z');
const NEXT_WEEK = '2026-11-15';

function shift(id: number, name: string, startsAt: string, week = NEXT_WEEK): Shift {
  return {
    id,
    template_id: id,
    name,
    week_start: week,
    starts_at: startsAt,
    ends_at: startsAt,
    required_staff: 2,
  };
}

const SHIFTS = [
  shift(2, 'Evening', '2026-11-15T14:00:00Z'),
  shift(1, 'Morning', '2026-11-15T05:00:00Z'),
  shift(3, 'Morning', '2026-11-16T05:00:00Z'),
];

function answer(id: number, shiftId: number, status: Availability['status']): Availability {
  return { id, shift_id: shiftId, user_id: 1, status };
}

function setup(options: { answers?: Availability[]; scheduleExists?: boolean } = {}) {
  const api = {
    shifts: { list: vi.fn().mockResolvedValue(SHIFTS) },
    availabilities: {
      list: vi.fn().mockResolvedValue(options.answers ?? []),
      set: vi.fn(),
    },
    schedules: {
      get: options.scheduleExists
        ? vi.fn().mockResolvedValue({ id: 1 })
        : vi.fn().mockRejectedValue(new ApiError(404, 'schedule_not_found', 'None.')),
    },
  };
  const store = new AvailabilityStore({ api, now: () => NOW });
  return { api, store };
}

describe('AvailabilityStore.loadWeek', () => {
  it('opens on next week by default', () => {
    expect(setup().store.weekStart).toBe(NEXT_WEEK);
  });

  it("lists the week's shifts earliest first, an unanswered shift counting as unavailable", async () => {
    const { api, store } = setup({ answers: [answer(1, 1, 'preferred')] });
    await store.loadWeek(NEXT_WEEK);
    expect(api.shifts.list).toHaveBeenCalledWith(NEXT_WEEK);
    expect(api.availabilities.list).toHaveBeenCalledWith(NEXT_WEEK);
    expect(store.status).toBe('loaded');
    expect(store.rows.map((row) => [row.shift.id, row.status])).toEqual([
      [1, 'preferred'],
      [2, 'unavailable'],
      [3, 'unavailable'],
    ]);
  });

  it('shows the server message when loading fails', async () => {
    const { api, store } = setup();
    api.shifts.list.mockRejectedValue(
      new ApiError(0, 'network_error', 'Could not reach the server.'),
    );
    await store.loadWeek(NEXT_WEEK);
    expect(store.status).toBe('error');
    expect(store.error).toBe('Could not reach the server.');
  });

  it('is editable when the week has no schedule', async () => {
    const { store } = setup();
    await store.loadWeek(NEXT_WEEK);
    expect(store.isReadOnly).toBe(false);
    expect(store.readOnlyReason).toBeNull();
  });

  it('is read-only once a schedule exists for the week', async () => {
    const { store } = setup({ scheduleExists: true });
    await store.loadWeek(NEXT_WEEK);
    expect(store.isReadOnly).toBe(true);
    expect(store.readOnlyReason).toMatch(/schedule/i);
  });

  it('is read-only for a past week, without asking about a schedule', async () => {
    const { api, store } = setup();
    await store.loadWeek('2026-11-01');
    expect(store.isReadOnly).toBe(true);
    expect(store.readOnlyReason).toMatch(/past/i);
    expect(api.schedules.get).not.toHaveBeenCalled();
  });
});

describe('AvailabilityStore answers', () => {
  it('marks the form dirty after a change and clean after changing it back', async () => {
    const { store } = setup({ answers: [answer(1, 1, 'available')] });
    await store.loadWeek(NEXT_WEEK);
    expect(store.isDirty).toBe(false);
    store.setAnswer(1, 'preferred');
    expect(store.isDirty).toBe(true);
    store.setAnswer(1, 'available');
    expect(store.isDirty).toBe(false);
  });

  it('treats answering "unavailable" for an unanswered shift as no change', async () => {
    const { store } = setup();
    await store.loadWeek(NEXT_WEEK);
    store.setAnswer(2, 'unavailable');
    expect(store.isDirty).toBe(false);
  });

  it('ignores changes on a read-only week', async () => {
    const { store } = setup({ scheduleExists: true });
    await store.loadWeek(NEXT_WEEK);
    store.setAnswer(1, 'available');
    expect(store.isDirty).toBe(false);
  });
});

describe('AvailabilityStore.save', () => {
  it('sends the explicit answers of the week in one request and becomes clean', async () => {
    const { api, store } = setup({ answers: [answer(1, 1, 'available')] });
    await store.loadWeek(NEXT_WEEK);
    store.setAnswer(1, 'preferred');
    store.setAnswer(3, 'available');
    api.availabilities.set.mockResolvedValue([
      answer(1, 1, 'preferred'),
      answer(5, 3, 'available'),
    ]);
    const ok = await store.save();
    expect(ok).toBe(true);
    expect(api.availabilities.set).toHaveBeenCalledWith({
      week_start: NEXT_WEEK,
      items: [
        { shift_id: 1, status: 'preferred' },
        { shift_id: 3, status: 'available' },
      ],
    });
    expect(store.isDirty).toBe(false);
    expect(store.isSaving).toBe(false);
    expect(store.rows.map((row) => row.status)).toEqual(['preferred', 'unavailable', 'available']);
  });

  it('keeps the changes and shows the server message when saving fails', async () => {
    const { api, store } = setup();
    await store.loadWeek(NEXT_WEEK);
    store.setAnswer(1, 'available');
    api.availabilities.set.mockRejectedValue(
      new ApiError(500, 'internal_error', 'Something went wrong on our side.'),
    );
    expect(await store.save()).toBe(false);
    expect(store.saveError).toBe('Something went wrong on our side.');
    expect(store.isDirty).toBe(true);
    expect(store.isReadOnly).toBe(false);
  });

  it('turns read-only when the server says the week is locked', async () => {
    const { api, store } = setup();
    await store.loadWeek(NEXT_WEEK);
    store.setAnswer(1, 'available');
    api.availabilities.set.mockRejectedValue(
      new ApiError(409, 'availability_locked', 'This week is already scheduled.'),
    );
    await store.save();
    expect(store.isReadOnly).toBe(true);
    expect(store.saveError).toBe('This week is already scheduled.');
  });

  it('does nothing when nothing changed', async () => {
    const { api, store } = setup();
    await store.loadWeek(NEXT_WEEK);
    expect(await store.save()).toBe(true);
    expect(api.availabilities.set).not.toHaveBeenCalled();
  });
});
