import type { ApiClient } from './apiClient';
import type { TimeEntry } from './types/timeEntry';

export interface TimeEntryFilters {
  from?: string;
  to?: string;
  user_id?: number;
}

export function createTimeEntriesApi(client: ApiClient) {
  return {
    clockIn: () => client.post<TimeEntry>('/api/time-entries/clock-in'),
    clockOut: () => client.post<TimeEntry>('/api/time-entries/clock-out'),
    list: (filters: TimeEntryFilters = {}) =>
      client.get<TimeEntry[]>('/api/time-entries', { ...filters }),
  };
}
