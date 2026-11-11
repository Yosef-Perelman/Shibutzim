import type { User } from './user';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenOut {
  access_token: string;
  token_type: string;
  user: User;
}
