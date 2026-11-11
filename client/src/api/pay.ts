import type { ApiClient } from './apiClient';
import type { Pay, TeamPay } from './types/pay';

/** First and last work day, both inclusive (glossary: work-day range). */
export interface PayRange {
  from: string;
  to: string;
}

export function createPayApi(client: ApiClient) {
  return {
    /** Own pay, or anyone's for a manager. */
    get: (range: PayRange, user_id?: number) => client.get<Pay>('/api/pay', { ...range, user_id }),
    /** Managers only. */
    team: (range: PayRange) => client.get<TeamPay>('/api/pay/team', { ...range }),
  };
}
