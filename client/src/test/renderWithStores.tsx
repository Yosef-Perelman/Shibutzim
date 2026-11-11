import { MantineProvider } from '@mantine/core';
import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter } from 'react-router';
import { vi, type Mock } from 'vitest';

import type { Api } from '../api';
import { RootStore } from '../stores/RootStore';
import { StoreProvider } from '../stores/StoreContext';
import { createMemoryTokenStorage } from '../stores/tokenStorage';
import { theme } from '../theme';
import { makeToken, makeUser } from './fixtures';
import type { User } from '../api/types/user';

/** A fake API: every method is a vi.fn() the test can program, grouped like the real `Api`. */
export type FakeApi = { [R in keyof Api]: { [M in keyof Api[R]]: Mock } };

export function makeFakeApi(): FakeApi {
  const group = (...names: string[]) =>
    Object.fromEntries(names.map((name) => [name, vi.fn()])) as Record<string, Mock>;
  return {
    auth: group('login', 'me'),
    users: group('list'),
    shifts: group('list', 'generate'),
    availabilities: group('list', 'set'),
    schedules: group(
      'get',
      'generate',
      'publish',
      'addAssignment',
      'replaceAssignment',
      'removeAssignment',
    ),
    timeEntries: group('clockIn', 'clockOut', 'list'),
    pay: group('get', 'team'),
  } as FakeApi;
}

export interface RenderOptions {
  user?: User;
  api?: FakeApi;
  path?: string;
}

/** Renders a screen inside the providers, logged in as `user` (an employee by default). */
export async function renderWithStores(ui: ReactElement, options: RenderOptions = {}) {
  const api = options.api ?? makeFakeApi();
  const user = options.user ?? makeUser();
  const store = new RootStore({
    api: api as unknown as Api,
    storage: createMemoryTokenStorage(),
  });
  api.auth.login.mockResolvedValue(makeToken(user));
  api.auth.me.mockResolvedValue(user);
  await store.auth.login(user.email, 'pw');
  await store.auth.restore();
  const view = render(
    <MantineProvider theme={theme} env="test">
      <StoreProvider store={store}>
        <MemoryRouter initialEntries={[options.path ?? '/']}>{ui}</MemoryRouter>
      </StoreProvider>
    </MantineProvider>,
  );
  return { ...view, api, store };
}
