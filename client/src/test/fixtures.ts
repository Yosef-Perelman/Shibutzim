// Small DTO factories for store and screen tests.
import type { TokenOut } from '../api/types/auth';
import type { User } from '../api/types/user';

export function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 1,
    email: 'noa@shibutzim.example',
    name: 'Noa Katz',
    role: 'employee',
    hourly_rate: '42.50',
    is_active: true,
    ...overrides,
  };
}

export function makeToken(user: User = makeUser(), accessToken = 'token-1'): TokenOut {
  return { access_token: accessToken, token_type: 'bearer', user };
}
