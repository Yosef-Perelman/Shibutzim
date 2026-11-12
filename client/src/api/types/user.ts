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

/** `UserCreate`: a manager adds a person. `hourly_rate` stays a string; the password is never echoed. */
export interface NewUser {
  email: string;
  name: string;
  role: Role;
  hourly_rate: string;
  password: string;
}
