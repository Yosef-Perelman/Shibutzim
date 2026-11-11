import { MantineProvider } from '@mantine/core';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import type { Api } from '../api';
import { StoreProvider } from '../stores/StoreContext';
import { RootStore } from '../stores/RootStore';
import { createMemoryTokenStorage } from '../stores/tokenStorage';
import { makeToken, makeUser } from '../test/fixtures';
import { theme } from '../theme';
import { AppRoutes } from './AppRoutes';

async function renderAt(path: string, user: ReturnType<typeof makeUser> | null) {
  const api = { auth: { login: vi.fn(), me: vi.fn() } };
  const store = new RootStore({ api: api as unknown as Api, storage: createMemoryTokenStorage() });
  if (user) {
    api.auth.login.mockResolvedValue(makeToken(user));
    api.auth.me.mockResolvedValue(user);
    await store.auth.login(user.email, 'pw');
  }
  await store.auth.restore();
  render(
    <MantineProvider theme={theme}>
      <StoreProvider store={store}>
        <MemoryRouter initialEntries={[path]}>
          <AppRoutes />
        </MemoryRouter>
      </StoreProvider>
    </MantineProvider>,
  );
}

const employee = makeUser();
const manager = makeUser({
  id: 9,
  name: 'Dana Levi',
  email: 'dana@shibutzim.example',
  role: 'manager',
});

describe('role routes', () => {
  it('sends someone who is not logged in to the login screen', async () => {
    await renderAt('/me/shifts', null);
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument();
  });

  it('lets an employee open their own screens', async () => {
    await renderAt('/me/availability', employee);
    expect(await screen.findByRole('heading', { name: 'Availability' })).toBeInTheDocument();
  });

  it('sends an employee away from manager screens', async () => {
    await renderAt('/manager/schedule', employee);
    expect(await screen.findByRole('heading', { name: 'My shifts' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Schedule' })).not.toBeInTheDocument();
  });

  it('shows a manager the manager navigation and the schedule', async () => {
    await renderAt('/manager/schedule', manager);
    expect(await screen.findByRole('heading', { name: 'Schedule' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Team pay' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Availability' })).not.toBeInTheDocument();
  });

  it('sends a logged-in person away from the login screen to their home', async () => {
    await renderAt('/login', manager);
    expect(await screen.findByRole('heading', { name: 'Schedule' })).toBeInTheDocument();
  });

  it('sends an unknown address to the role home', async () => {
    await renderAt('/nowhere', employee);
    expect(await screen.findByRole('heading', { name: 'My shifts' })).toBeInTheDocument();
  });
});
