import type { ApiClient } from './apiClient';
import type { Role } from './types/enums';
import type { NewUser, User } from './types/user';

export interface UserFilters {
  role?: Role;
  is_active?: boolean;
}

export function createUsersApi(client: ApiClient) {
  return {
    /** Managers only. */
    list: (filters: UserFilters = {}) => client.get<User[]>('/api/users', { ...filters }),
    /** Managers only: adds a person who can sign in with the initial password. */
    create: (body: NewUser) => client.post<User>('/api/users', body),
    /** Managers only: deactivates or reactivates; a person is never deleted. */
    setActive: (userId: number, isActive: boolean) =>
      client.patch<User>(`/api/users/${userId}`, { is_active: isActive }),
  };
}
