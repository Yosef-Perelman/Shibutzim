import { describe, expect, it, vi } from 'vitest';

import { ApiError } from '../api/apiClient';
import type { TimeEntry } from '../api/types/timeEntry';
import { TimeStore } from './TimeStore';

// Monday 9 Nov 2026, 14:00 Jerusalem.
const NOW = new Date('2026-11-09T12:00:00Z');

function entry(id: number, clockIn: string, clockOut: string | null): TimeEntry {
  return {
    id,
    user_id: 1,
    clock_in: clockIn,
    clock_out: clockOut,
    source: 'clock',
    created_by: 1,
    note: null,
  };
}

const CLOSED = entry(1, '2026-11-08T05:00:00Z', '2026-11-08T13:00:00Z');
const OPEN = entry(2, '2026-11-09T05:02:00Z', null);

function setup() {
  const api = {
    timeEntries: { list: vi.fn(), clockIn: vi.fn(), clockOut: vi.fn() },
  };
  const store = new TimeStore({ api, now: () => NOW });
  return { api, store };
}

describe('TimeStore.load', () => {
  it('finds the open entry among the recent ones', async () => {
    const { api, store } = setup();
    api.timeEntries.list.mockResolvedValue([CLOSED, OPEN]);
    await store.load();
    expect(store.status).toBe('loaded');
    expect(store.openEntry?.id).toBe(2);
    expect(store.isClockedIn).toBe(true);
  });

  it('is not clocked in when every entry is closed', async () => {
    const { api, store } = setup();
    api.timeEntries.list.mockResolvedValue([CLOSED]);
    await store.load();
    expect(store.isClockedIn).toBe(false);
    expect(store.openEntry).toBeNull();
  });

  it('looks back a week from today in Jerusalem, so an entry open since yesterday is found', async () => {
    const { api, store } = setup();
    api.timeEntries.list.mockResolvedValue([]);
    await store.load();
    expect(api.timeEntries.list).toHaveBeenCalledWith({ from: '2026-11-02', to: '2026-11-09' });
  });

  it('shows the server message when loading fails', async () => {
    const { api, store } = setup();
    api.timeEntries.list.mockRejectedValue(
      new ApiError(0, 'network_error', 'Could not reach the server.'),
    );
    await store.load();
    expect(store.status).toBe('error');
    expect(store.error).toBe('Could not reach the server.');
  });
});

describe('TimeStore.clockIn', () => {
  it('opens an entry', async () => {
    const { api, store } = setup();
    api.timeEntries.clockIn.mockResolvedValue(OPEN);
    expect(await store.clockIn()).toBe(true);
    expect(store.openEntry?.id).toBe(2);
    expect(store.isClockedIn).toBe(true);
  });

  it('is busy while the request runs', async () => {
    const { api, store } = setup();
    let finish: (value: TimeEntry) => void = () => undefined;
    api.timeEntries.clockIn.mockReturnValue(new Promise((resolve) => (finish = resolve)));
    const pending = store.clockIn();
    expect(store.isBusy).toBe(true);
    finish(OPEN);
    await pending;
    expect(store.isBusy).toBe(false);
  });

  it('shows the server message and syncs when already clocked in elsewhere', async () => {
    const { api, store } = setup();
    api.timeEntries.clockIn.mockRejectedValue(
      new ApiError(409, 'already_clocked_in', 'You are already clocked in.'),
    );
    api.timeEntries.list.mockResolvedValue([OPEN]);
    expect(await store.clockIn()).toBe(false);
    expect(store.actionError).toBe('You are already clocked in.');
    expect(store.isClockedIn).toBe(true);
  });
});

describe('TimeStore.clockOut', () => {
  it('closes the entry', async () => {
    const { api, store } = setup();
    api.timeEntries.list.mockResolvedValue([OPEN]);
    await store.load();
    api.timeEntries.clockOut.mockResolvedValue({ ...OPEN, clock_out: '2026-11-09T13:00:00Z' });
    expect(await store.clockOut()).toBe(true);
    expect(store.isClockedIn).toBe(false);
  });

  it('shows the server message and syncs when not clocked in', async () => {
    const { api, store } = setup();
    api.timeEntries.list.mockResolvedValue([OPEN]);
    await store.load();
    api.timeEntries.clockOut.mockRejectedValue(
      new ApiError(409, 'not_clocked_in', 'You are not clocked in.'),
    );
    api.timeEntries.list.mockResolvedValue([CLOSED]);
    expect(await store.clockOut()).toBe(false);
    expect(store.actionError).toBe('You are not clocked in.');
    expect(store.isClockedIn).toBe(false);
  });

  it('clears an earlier action error on the next attempt', async () => {
    const { api, store } = setup();
    api.timeEntries.clockIn.mockRejectedValueOnce(
      new ApiError(500, 'internal_error', 'Something went wrong.'),
    );
    await store.clockIn();
    expect(store.actionError).toBe('Something went wrong.');
    api.timeEntries.clockIn.mockResolvedValueOnce(OPEN);
    await store.clockIn();
    expect(store.actionError).toBeNull();
  });
});
