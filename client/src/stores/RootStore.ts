import { ApiClient } from '../api/apiClient';
import { createApi, type Api } from '../api';
import { AuthStore } from './AuthStore';
import { AvailabilityStore } from './AvailabilityStore';
import { PayStore } from './PayStore';
import { ScheduleStore } from './ScheduleStore';
import { createLocalTokenStorage, type TokenStorage } from './tokenStorage';

export interface RootStoreOptions {
  /** Tests pass a fake; the app builds the real one. */
  api?: Api;
  storage?: TokenStorage;
  demoUsers?: string[];
}

/** Demo accounts come from `VITE_DEMO_USERS` (comma-separated emails) and only in development. */
function configuredDemoUsers(): string[] {
  if (!import.meta.env.DEV) return [];
  const raw = import.meta.env.VITE_DEMO_USERS ?? '';
  return raw
    .split(',')
    .map((email) => email.trim())
    .filter(Boolean);
}

/** One store per domain, created once and shared through React context (architecture §9). */
export class RootStore {
  readonly api: Api;
  readonly auth: AuthStore;
  readonly schedule: ScheduleStore;
  readonly availability: AvailabilityStore;
  readonly pay: PayStore;

  constructor(options: RootStoreOptions = {}) {
    this.api =
      options.api ??
      createApi(
        new ApiClient({
          getToken: () => this.auth.token,
          onUnauthorized: () => this.auth.expireSession(),
        }),
      );
    this.auth = new AuthStore({
      api: this.api,
      storage: options.storage ?? createLocalTokenStorage(),
      demoUsers: options.demoUsers ?? configuredDemoUsers(),
    });
    this.schedule = new ScheduleStore({
      api: this.api,
      currentUserId: () => this.auth.user?.id ?? null,
    });
    this.availability = new AvailabilityStore({ api: this.api });
    this.pay = new PayStore({ api: this.api });
  }
}
