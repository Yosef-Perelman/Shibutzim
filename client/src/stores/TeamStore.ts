import { makeAutoObservable, runInAction } from 'mobx';

import { ApiError, INTERNAL_ERROR_MESSAGE } from '../api/apiClient';
import type { Api } from '../api';
import type { NewUser, User } from '../api/types/user';
import { failure, OK, type ActionResult, type LoadStatus } from './ScheduleStore';

export interface TeamStoreOptions {
  api: { users: Pick<Api['users'], 'list' | 'create' | 'setActive'> };
}

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : INTERNAL_ERROR_MESSAGE;
}

/** The people of the team, for the manager's Team screen: add a person, deactivate, reactivate. */
export class TeamStore {
  users: User[] = [];
  status: LoadStatus = 'idle';
  error: string | null = null;

  private readonly api: TeamStoreOptions['api'];
  private requestId = 0;

  constructor(options: TeamStoreOptions) {
    this.api = options.api;
    makeAutoObservable<TeamStore, 'api' | 'requestId'>(this, { api: false, requestId: false });
  }

  /** Everyone, active or not, by name; the server decides who may see this list. */
  get people(): User[] {
    return [...this.users].sort((a, b) => a.name.localeCompare(b.name) || a.id - b.id);
  }

  async load(): Promise<void> {
    const requestId = ++this.requestId;
    this.status = 'loading';
    this.error = null;
    try {
      const users = await this.api.users.list();
      if (requestId !== this.requestId) return;
      runInAction(() => {
        this.users = users;
        this.status = 'loaded';
      });
    } catch (error) {
      if (requestId !== this.requestId) return;
      runInAction(() => {
        this.users = [];
        this.status = 'error';
        this.error = messageOf(error);
      });
    }
  }

  async addPerson(input: NewUser): Promise<ActionResult> {
    try {
      const created = await this.api.users.create(input);
      runInAction(() => {
        this.users = [...this.users, created];
      });
      return OK;
    } catch (error) {
      return failure(error);
    }
  }

  async setActive(user: User, isActive: boolean): Promise<ActionResult> {
    try {
      const changed = await this.api.users.setActive(user.id, isActive);
      runInAction(() => {
        this.users = this.users.map((item) => (item.id === changed.id ? changed : item));
      });
      return OK;
    } catch (error) {
      return failure(error);
    }
  }
}
