import { describe, expect, it, vi } from 'vitest';

import { ApiError } from '../api/apiClient';
import type { Pay, TeamPay } from '../api/types/pay';
import { PayStore } from './PayStore';

const NOW = new Date('2026-11-09T12:00:00Z');
const NOVEMBER = { from: '2026-11-01', to: '2026-11-30' };
const OCTOBER = { from: '2026-10-01', to: '2026-10-31' };

function makePay(overrides: Partial<Pay> = {}): Pay {
  return {
    user_id: 1,
    from: NOVEMBER.from,
    to: NOVEMBER.to,
    days: [],
    seconds: 0,
    hours: '0.00',
    amount: '0.00',
    open_entries: 0,
    ...overrides,
  };
}

function makeTeam(): TeamPay {
  return {
    from: NOVEMBER.from,
    to: NOVEMBER.to,
    users: [],
    seconds: 0,
    hours: '0.00',
    amount: '0.00',
  };
}

function setup() {
  const api = { pay: { get: vi.fn(), team: vi.fn() } };
  const store = new PayStore({ api, now: () => NOW });
  return { api, store };
}

describe('PayStore month', () => {
  it('opens on the current month', () => {
    const { store } = setup();
    expect(store.monthStart).toBe('2026-11-01');
    expect(store.range).toEqual(NOVEMBER);
  });
});

describe('PayStore.loadPay', () => {
  it('loads own pay for the month and keeps the amounts as strings', async () => {
    const { api, store } = setup();
    api.pay.get.mockResolvedValue(makePay({ amount: '412.50', hours: '9.00' }));
    await store.loadPay();
    expect(api.pay.get).toHaveBeenCalledWith(NOVEMBER, undefined);
    expect(store.payStatus).toBe('loaded');
    expect(store.pay?.amount).toBe('412.50');
  });

  it('asks for another employee when a manager looks one up', async () => {
    const { api, store } = setup();
    api.pay.get.mockResolvedValue(makePay({ user_id: 3 }));
    await store.loadPay(3);
    expect(api.pay.get).toHaveBeenCalledWith(NOVEMBER, 3);
  });

  it('is loading while the request runs', async () => {
    const { api, store } = setup();
    let finish: (value: Pay) => void = () => undefined;
    api.pay.get.mockReturnValue(new Promise((resolve) => (finish = resolve)));
    const pending = store.loadPay();
    expect(store.payStatus).toBe('loading');
    finish(makePay());
    await pending;
    expect(store.payStatus).toBe('loaded');
  });

  it('knows a month with no entries has no days', async () => {
    const { api, store } = setup();
    api.pay.get.mockResolvedValue(makePay());
    await store.loadPay();
    expect(store.hasDays).toBe(false);
  });

  it('shows the server message on failure and can retry', async () => {
    const { api, store } = setup();
    api.pay.get.mockRejectedValueOnce(new ApiError(403, 'forbidden', 'You cannot see that.'));
    await store.loadPay();
    expect(store.payStatus).toBe('error');
    expect(store.payError).toBe('You cannot see that.');
    api.pay.get.mockResolvedValueOnce(makePay());
    await store.reloadPay();
    expect(store.payStatus).toBe('loaded');
    expect(store.payError).toBeNull();
  });

  it('ignores a slow answer for a month the user already left', async () => {
    const { api, store } = setup();
    let finishOld: (value: Pay) => void = () => undefined;
    api.pay.get.mockReturnValueOnce(new Promise((resolve) => (finishOld = resolve)));
    const old = store.loadPay();
    api.pay.get.mockResolvedValueOnce(makePay({ amount: '1.00' }));
    await store.loadPay();
    finishOld(makePay({ amount: '999.00' }));
    await old;
    expect(store.pay?.amount).toBe('1.00');
  });
});

describe('PayStore.loadTeam', () => {
  it('loads the team table for the month', async () => {
    const { api, store } = setup();
    api.pay.team.mockResolvedValue(makeTeam());
    await store.loadTeam();
    expect(api.pay.team).toHaveBeenCalledWith(NOVEMBER);
    expect(store.teamStatus).toBe('loaded');
    expect(store.team).not.toBeNull();
  });

  it('reports a failure separately from own pay', async () => {
    const { api, store } = setup();
    api.pay.team.mockRejectedValue(new ApiError(403, 'forbidden', 'Managers only.'));
    await store.loadTeam();
    expect(store.teamStatus).toBe('error');
    expect(store.teamError).toBe('Managers only.');
    expect(store.payStatus).toBe('idle');
  });
});

describe('PayStore.goToMonth', () => {
  it('reloads everything that was loaded for the new month', async () => {
    const { api, store } = setup();
    api.pay.get.mockResolvedValue(makePay());
    api.pay.team.mockResolvedValue(makeTeam());
    await store.loadPay(3);
    await store.loadTeam();
    api.pay.get.mockClear();
    api.pay.team.mockClear();
    await store.goToMonth(-1);
    expect(store.monthStart).toBe('2026-10-01');
    expect(api.pay.get).toHaveBeenCalledWith(OCTOBER, 3);
    expect(api.pay.team).toHaveBeenCalledWith(OCTOBER);
  });

  it('does not call the server for something that was never loaded', async () => {
    const { api, store } = setup();
    await store.goToMonth(1);
    expect(api.pay.get).not.toHaveBeenCalled();
    expect(api.pay.team).not.toHaveBeenCalled();
    expect(store.monthStart).toBe('2026-12-01');
  });
});

describe('PayStore.closePay', () => {
  it('forgets the drill-down so a month change no longer reloads it', async () => {
    const { api, store } = setup();
    api.pay.get.mockResolvedValue(makePay({ user_id: 3 }));
    api.pay.team.mockResolvedValue(makeTeam());
    await store.loadPay(3);
    await store.loadTeam();
    store.closePay();
    expect(store.pay).toBeNull();
    expect(store.payStatus).toBe('idle');
    api.pay.get.mockClear();
    await store.goToMonth(1);
    expect(api.pay.get).not.toHaveBeenCalled();
    expect(api.pay.team).toHaveBeenLastCalledWith({ from: '2026-12-01', to: '2026-12-31' });
  });

  it('ignores an answer that arrives after the drill-down was closed', async () => {
    const { api, store } = setup();
    let finish: (value: Pay) => void = () => undefined;
    api.pay.get.mockReturnValue(new Promise((resolve) => (finish = resolve)));
    const pending = store.loadPay(3);
    store.closePay();
    finish(makePay({ user_id: 3 }));
    await pending;
    expect(store.pay).toBeNull();
  });
});
