import type { ApiClient } from './apiClient';
import type { Role } from './types/enums';
import type { User } from './types/user';

export interface UserFilters {
  role?: Role;
  is_active?: boolean;
}

export function createUsersApi(client: ApiClient) {
  return {
    /** Managers only. */
    list: (filters: UserFilters = {}) => client.get<User[]>('/api/users', { ...filters }),
  };
}
