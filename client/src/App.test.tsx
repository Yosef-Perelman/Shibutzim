import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { App } from './App';
import { RootStore } from './stores/RootStore';
import { createMemoryTokenStorage } from './stores/tokenStorage';
import type { Api } from './api';

function fakeApi() {
  return { auth: { login: vi.fn(), me: vi.fn() } } as unknown as Api;
}

afterEach(() => window.history.pushState({}, '', '/'));

describe('App', () => {
  it('shows the login screen to someone who is not logged in', async () => {
    const store = new RootStore({ api: fakeApi(), storage: createMemoryTokenStorage() });
    render(<App store={store} />);
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Shibutzim' })).toBeInTheDocument();
  });
});
