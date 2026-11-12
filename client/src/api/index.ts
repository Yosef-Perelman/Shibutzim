import type { ApiClient } from './apiClient';
import { createAssistantApi } from './assistant';
import { createAuthApi } from './auth';
import { createAvailabilitiesApi } from './availabilities';
import { createPayApi } from './pay';
import { createSchedulesApi } from './schedules';
import { createShiftsApi } from './shifts';
import { createTimeEntriesApi } from './timeEntries';
import { createUsersApi } from './users';

/** Every resource module on one object; stores receive it, so tests can pass a fake. */
export function createApi(client: ApiClient) {
  return {
    auth: createAuthApi(client),
    users: createUsersApi(client),
    shifts: createShiftsApi(client),
    availabilities: createAvailabilitiesApi(client),
    schedules: createSchedulesApi(client),
    timeEntries: createTimeEntriesApi(client),
    pay: createPayApi(client),
    assistant: createAssistantApi(client),
  };
}

export type Api = ReturnType<typeof createApi>;
