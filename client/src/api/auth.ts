import type { ApiClient } from './apiClient';
import type { LoginRequest, TokenOut } from './types/auth';
import type { User } from './types/user';

export function createAuthApi(client: ApiClient) {
  return {
    login: (request: LoginRequest) => client.post<TokenOut>('/api/auth/login', request),
    me: () => client.get<User>('/api/auth/me'),
  };
}
