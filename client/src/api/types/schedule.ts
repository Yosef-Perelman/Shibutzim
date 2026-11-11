import type { ScheduleStatus } from './enums';

export type Constraint = 'availability' | 'overlap' | 'min_rest' | 'max_shifts';

export interface Assignment {
  id: number;
  shift_id: number;
  user_id: number;
  user_name: string;
  starts_at: string;
  ends_at: string;
}

export interface ShiftCoverage {
  shift_id: number;
  name: string;
  starts_at: string;
  ends_at: string;
  required_staff: number;
  assigned_count: number;
  unfilled_count: number;
}

export interface Schedule {
  id: number;
  week_start: string;
  status: ScheduleStatus;
  published_at: string | null;
  assignments: Assignment[];
  shifts: ShiftCoverage[];
}

export interface Reason {
  user_id: number;
  user_name: string;
  constraint: Constraint;
  shift_id: number | null;
}

export interface UnfilledSlot {
  shift_id: number;
  required: number;
  assigned: number;
  missing: number;
  reasons: Reason[];
  sentence: string;
}

export interface Score {
  filled: number;
  preferred: number;
  spread_minutes: number;
  value: number;
}

export interface ScheduleGenerateOut {
  schedule: Schedule;
  unfilled: UnfilledSlot[];
  score: Score;
  /** False when the search budget ran out before the search finished. */
  complete: boolean;
  steps: number;
}

export interface AssignmentCreate {
  shift_id: number;
  user_id: number;
}

export interface AssignmentUpdate {
  user_id: number;
}

/** A rule an edit bent but did not block: availability_ignored, max_shifts_exceeded, shift_overstaffed. */
export interface Warning {
  code: string;
  message: string;
}

export interface AssignmentEditOut {
  assignment: Assignment;
  warnings: Warning[];
}
