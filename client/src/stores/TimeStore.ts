import { makeAutoObservable, runInAction } from 'mobx';

import { ApiError, INTERNAL_ERROR_MESSAGE } from '../api/apiClient';
import type { Api } from '../api';
import type { TimeEntry } from '../api/types/timeEntry';
import { addDays, localToday } from '../lib/time';
import type { LoadStatus } from './ScheduleStore';

export interface TimeStoreOptions {
  api: { timeEntries: Pick<Api['timeEntries'], 'list' | 'clockIn' | 'clockOut'> };
  now?: () => Date;
}

// Entries are listed by work day. A forgotten clock-out can stay open for days, so look back a week.
const LOOKBACK_DAYS = 7;
const ALREADY_CLOCKED_IN = 'already_clocked_in';
const NOT_CLOCKED_IN = 'not_clocked_in';

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : INTERNAL_ERROR_MESSAGE;
}

/** The signed-in person's open time entry and the clock in / out actions (product-definition §5.3). */
export class TimeStore {
  openEntry: TimeEntry | null = null;
  status: LoadStatus = 'idle';
  error: string | null = null;
  isBusy = false;
  actionError: string | null = null;

  private readonly api: TimeStoreOptions['api'];
  private readonly now: () => Date;
  // Bumped by reset(): an answer to a request made before it belongs to nobody now.
  private epoch = 0;

  constructor(options: TimeStoreOptions) {
    this.api = options.api;
    this.now = options.now ?? (() => new Date());
    makeAutoObservable<TimeStore, 'api' | 'now' | 'epoch'>(this, {
      api: false,
      now: false,
      epoch: false,
    });
  }

  get isClockedIn(): boolean {
    return this.openEntry !== null;
  }

  reset(): void {
    this.epoch += 1;
    this.openEntry = null;
    this.status = 'idle';
    this.error = null;
    this.isBusy = false;
    this.actionError = null;
  }

  async load(): Promise<void> {
    const epoch = this.epoch;
    this.status = 'loading';
    this.error = null;
    const to = localToday(this.now());
    try {
      const entries = await this.api.timeEntries.list({ from: addDays(to, -LOOKBACK_DAYS), to });
      runInAction(() => {
        if (epoch !== this.epoch) return;
        this.openEntry = entries.find((entry) => entry.clock_out === null) ?? null;
        this.status = 'loaded';
      });
    } catch (error) {
      runInAction(() => {
        if (epoch !== this.epoch) return;
        this.status = 'error';
        this.error = messageOf(error);
      });
    }
  }

  async clockIn(): Promise<boolean> {
    return this.act(
      () => this.api.timeEntries.clockIn(),
      (entry) => entry,
      ALREADY_CLOCKED_IN,
    );
  }

  async clockOut(): Promise<boolean> {
    return this.act(
      () => this.api.timeEntries.clockOut(),
      () => null,
      NOT_CLOCKED_IN,
    );
  }

  /** Runs one action; when the server says our view was stale, show its message and reload. */
  private async act(
    request: () => Promise<TimeEntry>,
    nextOpenEntry: (result: TimeEntry) => TimeEntry | null,
    staleCode: string,
  ): Promise<boolean> {
    const epoch = this.epoch;
    this.isBusy = true;
    this.actionError = null;
    try {
      const result = await request();
      runInAction(() => {
        if (epoch === this.epoch) this.openEntry = nextOpenEntry(result);
      });
      return true;
    } catch (error) {
      runInAction(() => {
        if (epoch === this.epoch) this.actionError = messageOf(error);
      });
      if (epoch === this.epoch && error instanceof ApiError && error.code === staleCode) {
        await this.load();
      }
      return false;
    } finally {
      runInAction(() => {
        if (epoch === this.epoch) this.isBusy = false;
      });
    }
  }
}
