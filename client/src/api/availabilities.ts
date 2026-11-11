import type { ApiClient } from './apiClient';
import type { Availability, AvailabilitySet } from './types/availability';

export function createAvailabilitiesApi(client: ApiClient) {
  return {
    list: (week_start: string, user_id?: number) =>
      client.get<Availability[]>('/api/availabilities', { week_start, user_id }),
    set: (answers: AvailabilitySet) => client.put<Availability[]>('/api/availabilities', answers),
  };
}
