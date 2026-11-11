import type { TimeEntrySource } from './enums';

export interface TimeEntry {
  id: number;
  user_id: number;
  clock_in: string;
  /** Null while the entry is open. */
  clock_out: string | null;
  source: TimeEntrySource;
  created_by: number;
  note: string | null;
}
