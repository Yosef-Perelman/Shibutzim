import type { ApiClient } from './apiClient';
import type { Shift, ShiftGenerateOut } from './types/shift';

export function createShiftsApi(client: ApiClient) {
  return {
    list: (week_start: string) => client.get<Shift[]>('/api/shifts', { week_start }),
    /** Managers only: creates the week's missing shifts from the active templates. */
    generate: (week_start: string) =>
      client.post<ShiftGenerateOut>('/api/shifts/generate', { week_start }),
  };
}
