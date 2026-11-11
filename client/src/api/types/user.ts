import type { Role } from './enums';

/** `UserOut`. Money arrives as a string, never a number. */
export interface User {
  id: number;
  email: string;
  name: string;
  role: Role;
  hourly_rate: string;
  is_active: boolean;
}
