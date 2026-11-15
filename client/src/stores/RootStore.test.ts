import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Api } from '../api';
import { makeToken, makeUser } from '../test/fixtures';
import { makeFakeApi, type FakeApi } from '../test/renderWithStores';
import { parseDemoUsers, RootStore } from './RootStore';
import { createMemoryTokenStorage } from './tokenStorage';

function demoUsersOfNewStore(): string[] {
  const api = makeFakeApi() as unknown as Api;
  return new RootStore({ api, storage: createMemoryTokenStorage() }).auth.demoUsers;
}

afterEach(() => {
  vi.unstubAllEnvs();
});

describe('parseDemoUsers', () => {
  it('splits the comma-separated emails and drops spaces and empty entries', () => {
    expect(parseDemoUsers(' dana@x.example , noa@x.example,, ')).toEqual([
      'dana@x.example',
      'noa@x.example',
    ]);
  });

  it('is empty when the variable is missing or blank', () => {
    expect(parseDemoUsers(undefined)).toEqual([]);
    expect(parseDemoUsers('')).toEqual([]);
    expect(parseDemoUsers('  ')).toEqual([]);
  });
});

describe('the demo accounts of a RootStore', () => {
  it('are offered in development when VITE_DEMO_USERS is set', () => {
    vi.stubEnv('DEV', true);
    vi.stubEnv('VITE_DEMO_USERS', 'dana@x.example,noa@x.example');

    expect(demoUsersOfNewStore()).toEqual(['dana@x.example', 'noa@x.example']);
  });

  it('are offered in a production build too when VITE_DEMO_USERS was set at build time', () => {
    vi.stubEnv('DEV', false);
    vi.stubEnv('VITE_DEMO_USERS', 'dana@x.example');

    expect(demoUsersOfNewStore()).toEqual(['dana@x.example']);
  });

  it('are not offered when VITE_DEMO_USERS is empty, in development or in production', () => {
    vi.stubEnv('VITE_DEMO_USERS', '');

    vi.stubEnv('DEV', true);
    expect(demoUsersOfNewStore()).toEqual([]);
    vi.stubEnv('DEV', false);
    expect(demoUsersOfNewStore()).toEqual([]);
  });

  it('can be given explicitly, which wins over the environment', () => {
    vi.stubEnv('VITE_DEMO_USERS', 'dana@x.example');
    const api = makeFakeApi() as unknown as Api;

    const store = new RootStore({
      api,
      storage: createMemoryTokenStorage(),
      demoUsers: ['omer@x.example'],
    });

    expect(store.auth.demoUsers).toEqual(['omer@x.example']);
  });
});

describe('a RootStore when the session is cleared', () => {
  const dana = makeUser({ id: 9, email: 'dana@x.example', name: 'Dana Levi', role: 'manager' });
  const noa = makeUser({ id: 1, email: 'noa@x.example', name: 'Noa Katz' });
  const reply = (message: string) => ({ message, citations: [], tool_calls: [], proposal: null });

  /** Dana is signed in and has used the assistant, pay, team, time, availability and schedule. */
  async function signedInWithData() {
    const api: FakeApi = makeFakeApi();
    api.auth.login.mockResolvedValueOnce(makeToken(dana, 't-dana'));
    api.assistant.chat.mockResolvedValue(reply("Dana's private answer"));
    api.pay.get.mockResolvedValue({
      user_id: 9,
      from: '2026-11-01',
      to: '2026-11-30',
      days: [],
      seconds: 28800,
      hours: '8.00',
      amount: '340.00',
      open_entries: 0,
    });
    api.users.list.mockResolvedValue([noa, dana]);
    api.timeEntries.list.mockResolvedValue([
      {
        id: 5,
        user_id: 9,
        clock_in: '2026-11-15T07:00:00Z',
        clock_out: null,
        source: 'clock',
        created_by: 9,
        note: null,
      },
    ]);
    api.shifts.list.mockResolvedValue([
      {
        id: 1,
        template_id: 1,
        name: 'Morning',
        week_start: '2026-11-15',
        starts_at: '2026-11-15T07:00:00',
        ends_at: '2026-11-15T15:00:00',
        required_staff: 2,
      },
    ]);
    api.availabilities.list.mockResolvedValue([]);
    api.schedules.get.mockRejectedValue(new Error('none'));

    const store = new RootStore({
      api: api as unknown as Api,
      storage: createMemoryTokenStorage(),
      demoUsers: [dana.email, noa.email],
    });
    await store.auth.login(dana.email, 'shared-pw');
    await store.assistant.send("Dana's private question");
    await store.pay.loadPay();
    await store.team.load();
    await store.time.load();
    await store.availability.loadWeek('2026-11-15');
    await store.schedule.loadEmployees();

    // The fixture really holds data, so "empty afterwards" means something.
    expect(store.assistant.messages).toHaveLength(2);
    expect(store.pay.pay?.amount).toBe('340.00');
    expect(store.team.users).toHaveLength(2);
    expect(store.time.isClockedIn).toBe(true);
    expect(store.availability.shifts).toHaveLength(1);
    expect(store.schedule.employees).toHaveLength(2);
    return { api, store };
  }

  function expectNothingOfTheLastPersonLeft(store: RootStore) {
    expect(store.assistant.messages).toEqual([]);
    expect(store.assistant.history).toEqual([]);
    expect(store.pay.pay).toBeNull();
    expect(store.team.users).toEqual([]);
    expect(store.time.openEntry).toBeNull();
    expect(store.time.isClockedIn).toBe(false);
    expect(store.availability.shifts).toEqual([]);
    expect(store.schedule.employees).toEqual([]);
  }

  it('is cleared when the user switches to another demo user', async () => {
    const { api, store } = await signedInWithData();
    api.auth.login.mockResolvedValueOnce(makeToken(noa, 't-noa'));

    const ok = await store.auth.switchTo(noa.email);

    expect(ok).toBe(true);
    expect(store.auth.user?.id).toBe(1);
    expectNothingOfTheLastPersonLeft(store);
  });

  it('is cleared on logout', async () => {
    const { store } = await signedInWithData();

    store.auth.logout();

    expect(store.auth.isAuthenticated).toBe(false);
    expectNothingOfTheLastPersonLeft(store);
  });

  it('is cleared when the session expires', async () => {
    const { store } = await signedInWithData();

    store.auth.expireSession();

    expect(store.auth.sessionExpired).toBe(true);
    expectNothingOfTheLastPersonLeft(store);
  });

  it('is cleared when a fresh login follows without a logout', async () => {
    const { api, store } = await signedInWithData();
    api.auth.login.mockResolvedValueOnce(makeToken(noa, 't-noa'));

    await store.auth.login(noa.email, 'pw');

    expectNothingOfTheLastPersonLeft(store);
  });

  it('is cleared even when the new login fails, because the old session is dropped first', async () => {
    const { api, store } = await signedInWithData();
    api.auth.login.mockRejectedValueOnce(new Error('network'));

    await store.auth.login(noa.email, 'bad');

    expectNothingOfTheLastPersonLeft(store);
  });

  it('drops an assistant reply that was still on its way when the user switched', async () => {
    const { api, store } = await signedInWithData();
    let answer: (value: unknown) => void = () => undefined;
    api.assistant.chat.mockReturnValue(new Promise((resolve) => (answer = resolve)));
    const sending = store.assistant.send('one more question');
    api.auth.login.mockResolvedValueOnce(makeToken(noa, 't-noa'));
    await store.auth.switchTo(noa.email);

    answer(reply("Dana's late answer"));
    await sending;

    expect(store.assistant.messages).toEqual([]);
    expect(store.assistant.isSending).toBe(false);
  });

  it('sends the new person only their own questions to the server', async () => {
    const { api, store } = await signedInWithData();
    api.auth.login.mockResolvedValueOnce(makeToken(noa, 't-noa'));
    await store.auth.switchTo(noa.email);
    api.assistant.chat.mockResolvedValue(reply('hello Noa'));

    await store.assistant.send('my hours?');

    expect(api.assistant.chat).toHaveBeenLastCalledWith([{ role: 'user', content: 'my hours?' }]);
  });
});
