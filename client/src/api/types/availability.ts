import type { AvailabilityStatus } from './enums';

export interface Availability {
  id: number;
  shift_id: number;
  user_id: number;
  status: AvailabilityStatus;
}

export interface AvailabilityItem {
  shift_id: number;
  status: AvailabilityStatus;
}

export interface AvailabilitySet {
  week_start: string;
  user_id?: number;
  items: AvailabilityItem[];
}
