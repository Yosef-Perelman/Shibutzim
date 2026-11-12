import { ApiClient } from '../api/apiClient';
import { createApi, type Api } from '../api';
import { AssistantStore } from './AssistantStore';
import { AuthStore } from './AuthStore';
import { AvailabilityStore } from './AvailabilityStore';
import { PayStore } from './PayStore';
import { ScheduleStore } from './ScheduleStore';
import { TeamStore } from './TeamStore';
import { TimeStore } from './TimeStore';
import { createLocalTokenStorage, type TokenStorage } from './tokenStorage';

export interface RootStoreOptions {
  /** Tests pass a fake; the app builds the real one. */
  api?: Api;
  storage?: TokenStorage;
  demoUsers?: string[];
}

/** The emails of a comma-separated list; blank entries and spaces are dropped. */
export function parseDemoUsers(raw: string | undefined): string[] {
  return (raw ?? '')
    .split(',')
    .map((email) => email.trim())
    .filter(Boolean);
}

/**
 * Demo accounts exist wherever `VITE_DEMO_USERS` was set when the client was built: a developer's
 * `.env.local`, or the Docker build of the public demo. Left empty, no switch is offered.
 */
function configuredDemoUsers(): string[] {
  return parseDemoUsers(import.meta.env.VITE_DEMO_USERS);
}

/** One store per domain, created once and shared through React context (architecture §9). */
export class RootStore {
  readonly api: Api;
  readonly auth: AuthStore;
  readonly schedule: ScheduleStore;
  readonly availability: AvailabilityStore;
  readonly pay: PayStore;
  readonly team: TeamStore;
  readonly time: TimeStore;
  readonly assistant: AssistantStore;

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
    this.team = new TeamStore({ api: this.api });
    this.time = new TimeStore({ api: this.api });
    this.assistant = new AssistantStore({ api: this.api });
  }
}
