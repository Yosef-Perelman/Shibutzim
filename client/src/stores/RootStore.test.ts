import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Api } from '../api';
import { makeFakeApi } from '../test/renderWithStores';
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
