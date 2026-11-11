import { makeAutoObservable, runInAction } from 'mobx';

import { ApiError, INTERNAL_ERROR_MESSAGE } from '../api/apiClient';
import type { Api } from '../api';
import type {
  Assignment,
  Schedule,
  ScheduleGenerateOut,
  ShiftCoverage,
  Warning,
} from '../api/types/schedule';
import type { ScheduleStatus } from '../api/types/enums';
import type { Shift } from '../api/types/shift';
import type { User } from '../api/types/user';
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

/**
 * What an action returns instead of throwing: a blocking error carries the server's code and message
 * so a dialog can show it inline; `warnings` are rules an edit bent (availability_ignored, ...).
 */
export type ActionResult =
  { ok: true; warnings: Warning[] } | { ok: false; code: string; message: string };

export interface ScheduleStoreOptions {
  api: Pick<Api, 'schedules' | 'shifts' | 'users'>;
  currentUserId: () => number | null;
  now?: () => Date;
}

const SCHEDULE_NOT_FOUND = 'schedule_not_found';
const OK: ActionResult = { ok: true, warnings: [] };

function failure(error: unknown): ActionResult {
  if (error instanceof ApiError) return { ok: false, code: error.code, message: error.message };
  return { ok: false, code: 'internal_error', message: INTERNAL_ERROR_MESSAGE };
}

/** A shift that has no schedule yet: nobody assigned, everyone missing. */
function uncovered(shift: Shift): ShiftCoverage {
  return {
    shift_id: shift.id,
    name: shift.name,
    starts_at: shift.starts_at,
    ends_at: shift.ends_at,
    required_staff: shift.required_staff,
    assigned_count: 0,
    unfilled_count: shift.required_staff,
  };
}

/**
 * The schedule of one week and how to show it. Employees read a published week; a manager's board
 * also loads the week's shifts (they exist before a schedule does) and edits the schedule. The
 * server decides what is allowed; this store only carries the answers.
 */
export class ScheduleStore {
  weekStart: string;
  schedule: Schedule | null = null;
  /** The week's shifts, loaded for the manager's board only. */
  shifts: Shift[] = [];
  status: LoadStatus = 'idle';
  error: string | null = null;
  /** What the solver reported the last time the manager pressed Generate for this week. */
  lastRun: ScheduleGenerateOut | null = null;
  employees: User[] = [];
  employeesError: string | null = null;
  /** True while a generate, publish, create-shifts or assignment edit is running. */
  isWorking = false;

  private readonly api: ScheduleStoreOptions['api'];
  private readonly currentUserId: () => number | null;
  private includeShifts = false;
  private requestId = 0;

  constructor(options: ScheduleStoreOptions) {
    this.api = options.api;
    this.currentUserId = options.currentUserId;
    this.weekStart = currentWeekStart(options.now?.());
    makeAutoObservable<ScheduleStore, 'api' | 'currentUserId' | 'includeShifts' | 'requestId'>(
      this,
      { api: false, currentUserId: false, includeShifts: false, requestId: false },
    );
  }

  get hasSchedule(): boolean {
    return this.schedule !== null;
  }

  get scheduleStatus(): ScheduleStatus | null {
    return this.schedule?.status ?? null;
  }

  /** The schedule's own coverage, or the bare shifts while the week has no schedule. */
  get coverage(): ShiftCoverage[] {
    return this.schedule ? this.schedule.shifts : this.shifts.map(uncovered);
  }

  get hasShifts(): boolean {
    return this.coverage.length > 0;
  }

  /** Generate never replaces a published schedule (product-definition §5.2). */
  get canGenerate(): boolean {
    return this.hasShifts && this.scheduleStatus !== 'published';
  }

  /** Every shift of the week, earliest first, with its people (own name first, then by name). */
  get entries(): ShiftEntry[] {
    const assignments = this.schedule?.assignments ?? [];
    const me = this.currentUserId();
    return [...this.coverage]
      .sort((a, b) => a.starts_at.localeCompare(b.starts_at) || a.shift_id - b.shift_id)
      .map((shift) => {
        const people = assignments
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

  /** The employee's view: one published schedule. */
  loadWeek(weekStart: string, withShifts = false): Promise<void> {
    return this.load(weekStart, withShifts);
  }

  /** The manager's board: the schedule (if any) and the shifts of the week. */
  loadBoard(weekStart: string): Promise<void> {
    return this.load(weekStart, true);
  }

  reload(): Promise<void> {
    return this.load(this.weekStart, this.includeShifts);
  }

  goToWeek(offset: number): Promise<void> {
    return this.load(shiftWeek(this.weekStart, offset), this.includeShifts);
  }

  async loadEmployees(): Promise<void> {
    try {
      const employees = await this.api.users.list({ role: 'employee', is_active: true });
      runInAction(() => {
        this.employees = employees;
        this.employeesError = null;
      });
    } catch (error) {
      const result = failure(error);
      runInAction(() => {
        this.employeesError = result.ok ? null : result.message;
      });
    }
  }

  /** Creates the week's missing shifts from the active templates, then shows them. */
  createShifts(): Promise<ActionResult> {
    return this.work(async () => {
      await this.api.shifts.generate(this.weekStart);
      await this.refresh();
      return OK;
    });
  }

  /** Runs the solver and keeps its draft and report; replaces the current draft. */
  generate(): Promise<ActionResult> {
    return this.work(async () => {
      const run = await this.api.schedules.generate(this.weekStart);
      runInAction(() => {
        this.schedule = run.schedule;
        this.lastRun = run;
      });
      return OK;
    });
  }

  publish(): Promise<ActionResult> {
    return this.work(async () => {
      const schedule = await this.api.schedules.publish(this.weekStart);
      runInAction(() => {
        this.schedule = schedule;
      });
      return OK;
    });
  }

  addAssignment(shiftId: number, userId: number): Promise<ActionResult> {
    return this.work(async () => {
      const edit = await this.api.schedules.addAssignment(this.weekStart, {
        shift_id: shiftId,
        user_id: userId,
      });
      await this.refresh();
      return { ok: true, warnings: edit.warnings };
    });
  }

  replaceAssignment(assignmentId: number, userId: number): Promise<ActionResult> {
    return this.work(async () => {
      const edit = await this.api.schedules.replaceAssignment(this.weekStart, assignmentId, {
        user_id: userId,
      });
      await this.refresh();
      return { ok: true, warnings: edit.warnings };
    });
  }

  removeAssignment(assignmentId: number): Promise<ActionResult> {
    return this.work(async () => {
      await this.api.schedules.removeAssignment(this.weekStart, assignmentId);
      await this.refresh();
      return OK;
    });
  }

  private async load(weekStart: string, withShifts: boolean): Promise<void> {
    const requestId = ++this.requestId;
    if (weekStart !== this.weekStart) this.lastRun = null;
    this.weekStart = weekStart;
    this.includeShifts = withShifts;
    this.status = 'loading';
    this.error = null;
    try {
      const { schedule, shifts } = await this.fetchWeek(weekStart, withShifts);
      if (requestId !== this.requestId) return;
      runInAction(() => {
        this.schedule = schedule;
        this.shifts = shifts;
        this.status = 'loaded';
      });
    } catch (error) {
      if (requestId !== this.requestId) return;
      runInAction(() => {
        this.schedule = null;
        this.shifts = [];
        this.status = 'error';
        this.error = error instanceof ApiError ? error.message : INTERNAL_ERROR_MESSAGE;
      });
    }
  }

  /** Re-reads the week after a change without the loading state, so the board does not flash. */
  private async refresh(): Promise<void> {
    const { schedule, shifts } = await this.fetchWeek(this.weekStart, this.includeShifts);
    runInAction(() => {
      this.schedule = schedule;
      this.shifts = shifts;
    });
  }

  private async fetchWeek(
    weekStart: string,
    withShifts: boolean,
  ): Promise<{ schedule: Schedule | null; shifts: Shift[] }> {
    const [schedule, shifts] = await Promise.all([
      this.fetchSchedule(weekStart),
      withShifts ? this.api.shifts.list(weekStart) : Promise.resolve<Shift[]>([]),
    ]);
    return { schedule, shifts };
  }

  /** No schedule (or an unpublished one an employee may not see) is a normal empty week. */
  private async fetchSchedule(weekStart: string): Promise<Schedule | null> {
    try {
      return await this.api.schedules.get(weekStart);
    } catch (error) {
      if (error instanceof ApiError && error.code === SCHEDULE_NOT_FOUND) return null;
      throw error;
    }
  }

  private async work(task: () => Promise<ActionResult>): Promise<ActionResult> {
    this.isWorking = true;
    try {
      return await task();
    } catch (error) {
      return failure(error);
    } finally {
      runInAction(() => {
        this.isWorking = false;
      });
    }
  }
}
