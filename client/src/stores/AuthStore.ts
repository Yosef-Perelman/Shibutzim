import { makeAutoObservable, runInAction } from 'mobx';

import { ApiError, INTERNAL_ERROR_MESSAGE } from '../api/apiClient';
import type { Api } from '../api';
import type { Role } from '../api/types/enums';
import type { User } from '../api/types/user';
import type { TokenStorage } from './tokenStorage';

export interface AuthStoreOptions {
  api: Pick<Api, 'auth'>;
  storage: TokenStorage;
  /** Seeded accounts the demo switch offers; empty in production. */
  demoUsers?: string[];
}

export const MANAGER_HOME = '/manager/schedule';
export const EMPLOYEE_HOME = '/me/shifts';

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : INTERNAL_ERROR_MESSAGE;
}

/** Who is logged in. The role only decides what is shown; the server stays the real guard. */
export class AuthStore {
  token: string | null = null;
  user: User | null = null;
  error: string | null = null;
  isBusy = false;
  /** True until the first `restore()` finishes, so the app never flashes the login screen. */
  isRestoring = true;
  /** Set when the server rejected a token we sent; the login screen explains it. */
  sessionExpired = false;
  readonly demoUsers: string[];

  private readonly api: Pick<Api, 'auth'>;
  private readonly storage: TokenStorage;
  // Kept in memory only, and only when demo users are configured, so the switch asks once.
  private rememberedPassword: string | null = null;

  constructor(options: AuthStoreOptions) {
    this.api = options.api;
    this.storage = options.storage;
    this.demoUsers = options.demoUsers ?? [];
    makeAutoObservable<AuthStore, 'api' | 'storage' | 'rememberedPassword'>(this, {
      api: false,
      storage: false,
      rememberedPassword: false,
      demoUsers: false,
    });
  }

  get isAuthenticated(): boolean {
    return this.token !== null && this.user !== null;
  }

  get role(): Role | null {
    return this.user?.role ?? null;
  }

  get isManager(): boolean {
    return this.role === 'manager';
  }

  get homePath(): string {
    return this.isManager ? MANAGER_HOME : EMPLOYEE_HOME;
  }

  /** Reads the stored token and asks the server who it belongs to. */
  async restore(): Promise<void> {
    const stored = this.storage.read();
    if (!stored) {
      runInAction(() => {
        this.isRestoring = false;
      });
      return;
    }
    this.token = stored;
    try {
      const user = await this.api.auth.me();
      runInAction(() => {
        this.user = user;
      });
    } catch (error) {
      runInAction(() => {
        this.clearSession();
        // A rejected token is the normal end of a session; anything else is worth showing.
        if (!(error instanceof ApiError && error.status === 401)) this.error = messageOf(error);
      });
    } finally {
      runInAction(() => {
        this.isRestoring = false;
      });
    }
  }

  async login(email: string, password: string): Promise<boolean> {
    // Drop the current session first: a wrong password must not look like an expired token.
    this.clearSession();
    this.isBusy = true;
    this.error = null;
    try {
      const result = await this.api.auth.login({ email: email.trim(), password });
      runInAction(() => {
        this.token = result.access_token;
        this.user = result.user;
        this.sessionExpired = false;
        this.rememberedPassword = this.demoUsers.length > 0 ? password : null;
        this.storage.write(result.access_token);
      });
      return true;
    } catch (error) {
      runInAction(() => {
        this.error = messageOf(error);
      });
      return false;
    } finally {
      runInAction(() => {
        this.isBusy = false;
      });
    }
  }

  /** Demo-user switch: log in as another seeded account with the password typed once. */
  async switchTo(email: string): Promise<boolean> {
    if (this.rememberedPassword === null || !this.demoUsers.includes(email)) return false;
    return this.login(email, this.rememberedPassword);
  }

  logout(): void {
    this.clearSession();
    this.rememberedPassword = null;
    this.sessionExpired = false;
    this.error = null;
  }

  /** The server rejected our token (expired or invalid): end the session and say why. */
  expireSession(): void {
    if (this.token === null) return;
    this.clearSession();
    this.rememberedPassword = null;
    this.sessionExpired = true;
  }

  private clearSession(): void {
    this.token = null;
    this.user = null;
    this.storage.clear();
  }
}
