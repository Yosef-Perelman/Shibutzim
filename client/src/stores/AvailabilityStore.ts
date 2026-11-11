import { makeAutoObservable, runInAction } from 'mobx';

import { ApiError, INTERNAL_ERROR_MESSAGE } from '../api/apiClient';
import type { Api } from '../api';
import type { AvailabilityStatus } from '../api/types/enums';
import type { Shift } from '../api/types/shift';
import { currentWeekStart, isPastWeek, shiftWeek } from '../lib/time';
import type { LoadStatus } from './ScheduleStore';

export interface AvailabilityStoreOptions {
  api: {
    shifts: Pick<Api['shifts'], 'list'>;
    availabilities: Pick<Api['availabilities'], 'list' | 'set'>;
    schedules: Pick<Api['schedules'], 'get'>;
  };
  now?: () => Date;
}

export interface AvailabilityRow {
  shift: Shift;
  status: AvailabilityStatus;
}

type Answers = Record<number, AvailabilityStatus>;

const DEFAULT_STATUS: AvailabilityStatus = 'unavailable';
const AVAILABILITY_LOCKED = 'availability_locked';

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : INTERNAL_ERROR_MESSAGE;
}

/**
 * One employee's answers for one week (product-definition §5.1). `saved` is what the server has,
 * `draft` what the form changed since. A shift with no answer counts as unavailable; the server
 * stays the real guard of the lock, the store only explains it.
 */
export class AvailabilityStore {
  weekStart: string;
  shifts: Shift[] = [];
  status: LoadStatus = 'idle';
  error: string | null = null;
  isSaving = false;
  saveError: string | null = null;

  private saved: Answers = {};
  private draft: Answers = {};
  private scheduleLocked = false;
  private readonly api: AvailabilityStoreOptions['api'];
  private readonly now: () => Date;
  private requestId = 0;

  constructor(options: AvailabilityStoreOptions) {
    this.api = options.api;
    this.now = options.now ?? (() => new Date());
    // The form opens on next week: that is the week employees answer for.
    this.weekStart = shiftWeek(currentWeekStart(this.now()), 1);
    makeAutoObservable<
      AvailabilityStore,
      'api' | 'now' | 'requestId' | 'saved' | 'draft' | 'scheduleLocked'
    >(this, {
      api: false,
      now: false,
      requestId: false,
      saved: true,
      draft: true,
      scheduleLocked: true,
    });
  }

  get rows(): AvailabilityRow[] {
    return [...this.shifts]
      .sort((a, b) => a.starts_at.localeCompare(b.starts_at) || a.id - b.id)
      .map((shift) => ({
        shift,
        status: this.draft[shift.id] ?? this.saved[shift.id] ?? DEFAULT_STATUS,
      }));
  }

  get isDirty(): boolean {
    return Object.keys(this.draft).length > 0;
  }

  get isReadOnly(): boolean {
    return isPastWeek(this.weekStart, this.now()) || this.scheduleLocked;
  }

  get readOnlyReason(): string | null {
    if (isPastWeek(this.weekStart, this.now())) {
      return 'This week is in the past, so your answers can no longer be changed.';
    }
    if (this.scheduleLocked) {
      return 'The schedule for this week already exists, so your answers can no longer be changed.';
    }
    return null;
  }

  async loadWeek(weekStart: string): Promise<void> {
    const requestId = ++this.requestId;
    this.weekStart = weekStart;
    this.status = 'loading';
    this.error = null;
    this.saveError = null;
    this.draft = {};
    this.scheduleLocked = false;
    try {
      const [shifts, answers] = await Promise.all([
        this.api.shifts.list(weekStart),
        this.api.availabilities.list(weekStart),
      ]);
      const locked = await this.hasSchedule(weekStart);
      if (requestId !== this.requestId) return;
      runInAction(() => {
        this.shifts = shifts;
        this.saved = Object.fromEntries(answers.map((row) => [row.shift_id, row.status]));
        this.scheduleLocked = locked;
        this.status = 'loaded';
      });
    } catch (error) {
      if (requestId !== this.requestId) return;
      runInAction(() => {
        this.status = 'error';
        this.error = messageOf(error);
      });
    }
  }

  reload(): Promise<void> {
    return this.loadWeek(this.weekStart);
  }

  goToWeek(offset: number): Promise<void> {
    return this.loadWeek(shiftWeek(this.weekStart, offset));
  }

  setAnswer(shiftId: number, status: AvailabilityStatus): void {
    if (this.isReadOnly) return;
    const baseline = this.saved[shiftId] ?? DEFAULT_STATUS;
    if (status === baseline) {
      delete this.draft[shiftId];
    } else {
      this.draft[shiftId] = status;
    }
  }

  /** Sends every explicit answer of the week in one request. Returns whether it worked. */
  async save(): Promise<boolean> {
    if (!this.isDirty) return true;
    const items = this.rows
      .filter(({ shift }) => shift.id in this.draft || shift.id in this.saved)
      .map(({ shift, status }) => ({ shift_id: shift.id, status }));
    this.isSaving = true;
    this.saveError = null;
    try {
      const rows = await this.api.availabilities.set({ week_start: this.weekStart, items });
      runInAction(() => {
        for (const row of rows) this.saved[row.shift_id] = row.status;
        this.draft = {};
      });
      return true;
    } catch (error) {
      runInAction(() => {
        this.saveError = messageOf(error);
        if (error instanceof ApiError && error.code === AVAILABILITY_LOCKED) {
          this.scheduleLocked = true;
        }
      });
      return false;
    } finally {
      runInAction(() => {
        this.isSaving = false;
      });
    }
  }

  /** Once a schedule is visible to the employee the week is locked; a past week needs no check. */
  private async hasSchedule(weekStart: string): Promise<boolean> {
    if (isPastWeek(weekStart, this.now())) return false;
    try {
      await this.api.schedules.get(weekStart);
      return true;
    } catch {
      // No schedule (or none the employee may see): the form stays open and the server decides.
      return false;
    }
  }
}
