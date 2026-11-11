import { makeAutoObservable, runInAction } from 'mobx';

import { ApiError, INTERNAL_ERROR_MESSAGE } from '../api/apiClient';
import type { Api } from '../api';
import type { PayRange } from '../api/pay';
import type { Pay, TeamPay } from '../api/types/pay';
import { currentMonthStart, monthRange, shiftMonth } from '../lib/time';
import type { LoadStatus } from './ScheduleStore';

export interface PayStoreOptions {
  api: { pay: Pick<Api['pay'], 'get' | 'team'> };
  now?: () => Date;
}

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : INTERNAL_ERROR_MESSAGE;
}

/**
 * Pay for one calendar month: a person's breakdown and the team table. The numbers are the server's;
 * the store keeps them as strings and never computes with them.
 */
export class PayStore {
  monthStart: string;
  pay: Pay | null = null;
  payStatus: LoadStatus = 'idle';
  payError: string | null = null;
  team: TeamPay | null = null;
  teamStatus: LoadStatus = 'idle';
  teamError: string | null = null;

  private readonly api: PayStoreOptions['api'];
  // What was asked for, so changing the month can reload it. `undefined` userId means "my own pay".
  private payRequested = false;
  private payUserId: number | undefined = undefined;
  private teamRequested = false;
  private payRequestId = 0;
  private teamRequestId = 0;

  constructor(options: PayStoreOptions) {
    this.api = options.api;
    this.monthStart = currentMonthStart(options.now?.());
    makeAutoObservable<
      PayStore,
      'api' | 'payRequested' | 'payUserId' | 'teamRequested' | 'payRequestId' | 'teamRequestId'
    >(this, {
      api: false,
      payRequested: false,
      payUserId: false,
      teamRequested: false,
      payRequestId: false,
      teamRequestId: false,
    });
  }

  get range(): PayRange {
    return monthRange(this.monthStart);
  }

  get hasDays(): boolean {
    return (this.pay?.days.length ?? 0) > 0;
  }

  /** Own pay (no `userId`) or, for a manager, one employee's. */
  async loadPay(userId?: number): Promise<void> {
    this.payRequested = true;
    this.payUserId = userId;
    const requestId = ++this.payRequestId;
    this.payStatus = 'loading';
    this.payError = null;
    try {
      const pay = await this.api.pay.get(this.range, userId);
      if (requestId !== this.payRequestId) return;
      runInAction(() => {
        this.pay = pay;
        this.payStatus = 'loaded';
      });
    } catch (error) {
      if (requestId !== this.payRequestId) return;
      runInAction(() => {
        this.pay = null;
        this.payStatus = 'error';
        this.payError = messageOf(error);
      });
    }
  }

  reloadPay(): Promise<void> {
    return this.loadPay(this.payUserId);
  }

  /** Managers only: every user's hours and amount for the month. */
  async loadTeam(): Promise<void> {
    this.teamRequested = true;
    const requestId = ++this.teamRequestId;
    this.teamStatus = 'loading';
    this.teamError = null;
    try {
      const team = await this.api.pay.team(this.range);
      if (requestId !== this.teamRequestId) return;
      runInAction(() => {
        this.team = team;
        this.teamStatus = 'loaded';
      });
    } catch (error) {
      if (requestId !== this.teamRequestId) return;
      runInAction(() => {
        this.team = null;
        this.teamStatus = 'error';
        this.teamError = messageOf(error);
      });
    }
  }

  /** Moves the month and reloads whatever was loaded. */
  async goToMonth(offset: number): Promise<void> {
    this.monthStart = shiftMonth(this.monthStart, offset);
    const loads: Promise<void>[] = [];
    if (this.payRequested) loads.push(this.loadPay(this.payUserId));
    if (this.teamRequested) loads.push(this.loadTeam());
    await Promise.all(loads);
  }

  /** Back to the current month, reloading whatever was loaded. */
  async goToCurrentMonth(now: Date = new Date()): Promise<void> {
    const target = currentMonthStart(now);
    const offset = monthsBetween(this.monthStart, target);
    if (offset !== 0) await this.goToMonth(offset);
  }
}

function monthsBetween(from: string, to: string): number {
  const [fromYear = 0, fromMonth = 0] = from.split('-').map(Number);
  const [toYear = 0, toMonth = 0] = to.split('-').map(Number);
  return (toYear - fromYear) * 12 + (toMonth - fromMonth);
}
