import type { Role } from './enums';

// Money and hours are decimal strings; `seconds` is exact, `hours` is rounded for display only.

export interface TierLine {
  from_hour: string;
  to_hour: string | null;
  multiplier: string;
  seconds: number;
  hours: string;
  amount: string;
}

export interface DayPay {
  work_day: string;
  seconds: number;
  hours: string;
  amount: string;
  lines: TierLine[];
}

/** `from` and `to` are the first and last work day, both inclusive. */
export interface Pay {
  user_id: number;
  from: string;
  to: string;
  days: DayPay[];
  seconds: number;
  hours: string;
  amount: string;
  open_entries: number;
}

export interface TeamPayRow {
  user_id: number;
  name: string;
  role: Role;
  hourly_rate: string;
  seconds: number;
  hours: string;
  amount: string;
  open_entries: number;
}

export interface TeamPay {
  from: string;
  to: string;
  users: TeamPayRow[];
  seconds: number;
  hours: string;
  amount: string;
}
