import { makeAutoObservable, runInAction } from 'mobx';

import { ApiError, INTERNAL_ERROR_MESSAGE } from '../api/apiClient';
import type { Api } from '../api';
import type { Assignment, Schedule, ShiftCoverage } from '../api/types/schedule';
import { currentWeekStart, localDate, shiftWeek } from '../lib/time';

export type LoadStatus = 'idle' | 'loading' | 'loaded' | 'error';

/** One shift of the week with the people on it; the current user's name comes first. */
export interface ShiftEntry {
  shift: ShiftCoverage;
  people: Assignment[];
  isMine: boolean;
}

export interface DayEntry {
  /** Local calendar date, `YYYY-MM-DD`. */
  date: string;
  shifts: ShiftEntry[];
}

export interface ScheduleStoreOptions {
  api: { schedules: Pick<Api['schedules'], 'get'> };
  currentUserId: () => number | null;
  now?: () => Date;
}

const SCHEDULE_NOT_FOUND = 'schedule_not_found';

/** The schedule of one week and how to show it. The server decides who may see which schedule. */
export class ScheduleStore {
  weekStart: string;
  schedule: Schedule | null = null;
  status: LoadStatus = 'idle';
  error: string | null = null;

  private readonly api: ScheduleStoreOptions['api'];
  private readonly currentUserId: () => number | null;
  private requestId = 0;

  constructor(options: ScheduleStoreOptions) {
    this.api = options.api;
    this.currentUserId = options.currentUserId;
    this.weekStart = currentWeekStart(options.now?.());
    makeAutoObservable<ScheduleStore, 'api' | 'currentUserId' | 'requestId'>(this, {
      api: false,
      currentUserId: false,
      requestId: false,
    });
  }

  get hasSchedule(): boolean {
    return this.schedule !== null;
  }

  /** Every shift of the week, earliest first, with its people (own name first, then by name). */
  get entries(): ShiftEntry[] {
    const schedule = this.schedule;
    if (!schedule) return [];
    const me = this.currentUserId();
    return [...schedule.shifts]
      .sort((a, b) => a.starts_at.localeCompare(b.starts_at) || a.shift_id - b.shift_id)
      .map((shift) => {
        const people = schedule.assignments
          .filter((assignment) => assignment.shift_id === shift.shift_id)
          .sort(
            (a, b) =>
              Number(b.user_id === me) - Number(a.user_id === me) ||
              a.user_name.localeCompare(b.user_name),
          );
        return { shift, people, isMine: people.some((person) => person.user_id === me) };
      });
  }

  /** The current user's own shifts, earliest first. */
  get mine(): ShiftEntry[] {
    return this.entries.filter((entry) => entry.isMine);
  }

  /** The whole team's shifts grouped by local day. */
  get days(): DayEntry[] {
    const byDate = new Map<string, ShiftEntry[]>();
    for (const entry of this.entries) {
      const date = localDate(entry.shift.starts_at);
      byDate.set(date, [...(byDate.get(date) ?? []), entry]);
    }
    return [...byDate.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, shifts]) => ({ date, shifts }));
  }

  async loadWeek(weekStart: string): Promise<void> {
    const requestId = ++this.requestId;
    this.weekStart = weekStart;
    this.status = 'loading';
    this.error = null;
    try {
      const schedule = await this.api.schedules.get(weekStart);
      if (requestId !== this.requestId) return;
      runInAction(() => {
        this.schedule = schedule;
        this.status = 'loaded';
      });
    } catch (error) {
      if (requestId !== this.requestId) return;
      runInAction(() => {
        this.schedule = null;
        if (error instanceof ApiError && error.code === SCHEDULE_NOT_FOUND) {
          // No schedule (or an unpublished one an employee may not see) is a normal empty week.
          this.status = 'loaded';
        } else {
          this.status = 'error';
          this.error = error instanceof ApiError ? error.message : INTERNAL_ERROR_MESSAGE;
        }
      });
    }
  }

  reload(): Promise<void> {
    return this.loadWeek(this.weekStart);
  }

  goToWeek(offset: number): Promise<void> {
    return this.loadWeek(shiftWeek(this.weekStart, offset));
  }
}
