export interface Shift {
  id: number;
  template_id: number;
  name: string;
  week_start: string;
  starts_at: string;
  ends_at: string;
  required_staff: number;
}

export interface ShiftGenerateOut {
  week_start: string;
  created: number;
  shifts: Shift[];
}
