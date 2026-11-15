import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../api/apiClient';
import { makeToken, makeUser } from '../test/fixtures';
import { AuthStore } from './AuthStore';
import { createMemoryTokenStorage } from './tokenStorage';

const manager = makeUser({
  id: 9,
  email: 'dana@shibutzim.example',
  name: 'Dana Levi',
  role: 'manager',
});

function setup(options: { storedToken?: string; demoUsers?: string[] } = {}) {
  const api = { auth: { login: vi.fn(), me: vi.fn() } };
  const storage = createMemoryTokenStorage(options.storedToken ?? null);
  const onSessionCleared = vi.fn();
  const store = new AuthStore({ api, storage, demoUsers: options.demoUsers, onSessionCleared });
  return { api, storage, store, onSessionCleared };
}

describe('AuthStore login', () => {
  let ctx: ReturnType<typeof setup>;
  beforeEach(() => {
    ctx = setup();
  });

  it('stores the token and the user after a successful login', async () => {
    ctx.api.auth.login.mockResolvedValue(makeToken(makeUser(), 'abc'));
    const ok = await ctx.store.login('noa@shibutzim.example', 'pw');
    expect(ok).toBe(true);
    expect(ctx.store.token).toBe('abc');
    expect(ctx.store.user?.name).toBe('Noa Katz');
    expect(ctx.store.isAuthenticated).toBe(true);
    expect(ctx.storage.read()).toBe('abc');
  });

  it('keeps the server message and stays logged out after a failed login', async () => {
    ctx.api.auth.login.mockRejectedValue(
      new ApiError(401, 'invalid_credentials', 'Wrong email or password.'),
    );
    const ok = await ctx.store.login('noa@shibutzim.example', 'bad');
    expect(ok).toBe(false);
    expect(ctx.store.error).toBe('Wrong email or password.');
    expect(ctx.store.isAuthenticated).toBe(false);
    expect(ctx.storage.read()).toBeNull();
  });

  it('is busy while the request runs', async () => {
    let finish: (value: ReturnType<typeof makeToken>) => void = () => undefined;
    ctx.api.auth.login.mockReturnValue(new Promise((resolve) => (finish = resolve)));
    const pending = ctx.store.login('noa@shibutzim.example', 'pw');
    expect(ctx.store.isBusy).toBe(true);
    finish(makeToken());
    await pending;
    expect(ctx.store.isBusy).toBe(false);
  });

  it('derives the role and the home path from the user', async () => {
    ctx.api.auth.login.mockResolvedValue(makeToken(manager));
    await ctx.store.login(manager.email, 'pw');
    expect(ctx.store.isManager).toBe(true);
    expect(ctx.store.homePath).toBe('/manager/schedule');
  });

  it('sends employees to their shifts', async () => {
    ctx.api.auth.login.mockResolvedValue(makeToken());
    await ctx.store.login('noa@shibutzim.example', 'pw');
    expect(ctx.store.isManager).toBe(false);
    expect(ctx.store.homePath).toBe('/me/shifts');
  });
});

describe('AuthStore session', () => {
  it('restores a stored token by asking the server who it belongs to', async () => {
    const { api, store } = setup({ storedToken: 'stored' });
    api.auth.me.mockResolvedValue(makeUser());
    await store.restore();
    expect(store.token).toBe('stored');
    expect(store.user?.email).toBe('noa@shibutzim.example');
    expect(store.isRestoring).toBe(false);
  });

  it('does not call the server when no token is stored', async () => {
    const { api, store } = setup();
    await store.restore();
    expect(api.auth.me).not.toHaveBeenCalled();
    expect(store.isAuthenticated).toBe(false);
    expect(store.isRestoring).toBe(false);
  });

  it('forgets a stored token the server rejects', async () => {
    const { api, storage, store } = setup({ storedToken: 'old' });
    api.auth.me.mockRejectedValue(new ApiError(401, 'token_expired', 'Your session expired.'));
    await store.restore();
    expect(store.isAuthenticated).toBe(false);
    expect(store.token).toBeNull();
    expect(storage.read()).toBeNull();
  });

  it('logs out and clears the stored token', async () => {
    const { api, storage, store } = setup();
    api.auth.login.mockResolvedValue(makeToken());
    await store.login('noa@shibutzim.example', 'pw');
    store.logout();
    expect(store.isAuthenticated).toBe(false);
    expect(storage.read()).toBeNull();
    expect(store.sessionExpired).toBe(false);
  });

  it('marks the session expired when the server rejects the token, then clears it on login', async () => {
    const { api, store } = setup();
    api.auth.login.mockResolvedValue(makeToken());
    await store.login('noa@shibutzim.example', 'pw');
    store.expireSession();
    expect(store.isAuthenticated).toBe(false);
    expect(store.sessionExpired).toBe(true);
    await store.login('noa@shibutzim.example', 'pw');
    expect(store.sessionExpired).toBe(false);
  });

  it('ignores an expiry signal when nobody is logged in', () => {
    const { store } = setup();
    store.expireSession();
    expect(store.sessionExpired).toBe(false);
  });
});

describe('AuthStore demo-user switch', () => {
  it('offers no demo users unless some are configured', () => {
    expect(setup().store.demoUsers).toEqual([]);
  });

  it('logs in as another demo user with the password typed once', async () => {
    const { api, store } = setup({
      demoUsers: ['dana@shibutzim.example', 'noa@shibutzim.example'],
    });
    api.auth.login.mockResolvedValueOnce(makeToken(manager, 't1'));
    await store.login('dana@shibutzim.example', 'shared-pw');
    api.auth.login.mockResolvedValueOnce(makeToken(makeUser(), 't2'));
    const ok = await store.switchTo('noa@shibutzim.example');
    expect(ok).toBe(true);
    expect(api.auth.login).toHaveBeenLastCalledWith({
      email: 'noa@shibutzim.example',
      password: 'shared-pw',
    });
    expect(store.user?.role).toBe('employee');
  });

  it('does not remember the password when no demo users are configured', async () => {
    const { api, store } = setup();
    api.auth.login.mockResolvedValue(makeToken());
    await store.login('noa@shibutzim.example', 'pw');
    expect(await store.switchTo('dana@shibutzim.example')).toBe(false);
  });
});

describe('AuthStore onSessionCleared', () => {
  it('is not called by constructing the store or by a restore with no stored token', async () => {
    const { store, onSessionCleared } = setup();
    await store.restore();
    expect(onSessionCleared).not.toHaveBeenCalled();
  });

  it('is called when someone logs in, so the previous person leaves nothing behind', async () => {
    const { api, store, onSessionCleared } = setup();
    api.auth.login.mockResolvedValue(makeToken());

    await store.login('noa@shibutzim.example', 'pw');

    expect(onSessionCleared).toHaveBeenCalledTimes(1);
  });

  it('is called even when the login fails, because the old session is dropped first', async () => {
    const { api, store, onSessionCleared } = setup();
    api.auth.login.mockRejectedValue(new ApiError(401, 'invalid_credentials', 'Wrong.'));

    await store.login('noa@shibutzim.example', 'bad');

    expect(onSessionCleared).toHaveBeenCalledTimes(1);
  });

  it('is called before the new user is set, never after', async () => {
    const { api, store, onSessionCleared } = setup();
    api.auth.login.mockResolvedValue(makeToken());
    onSessionCleared.mockImplementation(() => {
      expect(store.user).toBeNull();
      expect(store.token).toBeNull();
    });

    await store.login('noa@shibutzim.example', 'pw');

    expect(onSessionCleared).toHaveBeenCalled();
  });

  it('is called when switching to another demo user', async () => {
    const { api, store, onSessionCleared } = setup({
      demoUsers: ['dana@shibutzim.example', 'noa@shibutzim.example'],
    });
    api.auth.login.mockResolvedValueOnce(makeToken(manager, 't1'));
    await store.login('dana@shibutzim.example', 'shared-pw');
    onSessionCleared.mockClear();
    api.auth.login.mockResolvedValueOnce(makeToken(makeUser(), 't2'));

    await store.switchTo('noa@shibutzim.example');

    expect(onSessionCleared).toHaveBeenCalledTimes(1);
  });

  it('is called on logout', async () => {
    const { api, store, onSessionCleared } = setup();
    api.auth.login.mockResolvedValue(makeToken());
    await store.login('noa@shibutzim.example', 'pw');
    onSessionCleared.mockClear();

    store.logout();

    expect(onSessionCleared).toHaveBeenCalledTimes(1);
  });

  it('is called when the session expires', async () => {
    const { api, store, onSessionCleared } = setup();
    api.auth.login.mockResolvedValue(makeToken());
    await store.login('noa@shibutzim.example', 'pw');
    onSessionCleared.mockClear();

    store.expireSession();

    expect(onSessionCleared).toHaveBeenCalledTimes(1);
  });

  it('is not called by an expiry signal when nobody is logged in', () => {
    const { store, onSessionCleared } = setup();

    store.expireSession();

    expect(onSessionCleared).not.toHaveBeenCalled();
  });

  it('is called when a stored token is rejected on restore', async () => {
    const { api, store, onSessionCleared } = setup({ storedToken: 'old' });
    api.auth.me.mockRejectedValue(new ApiError(401, 'token_expired', 'Your session expired.'));

    await store.restore();

    expect(onSessionCleared).toHaveBeenCalledTimes(1);
  });

  it('is optional: the store works without it', async () => {
    const api = { auth: { login: vi.fn(), me: vi.fn() } };
    api.auth.login.mockResolvedValue(makeToken());
    const store = new AuthStore({ api, storage: createMemoryTokenStorage() });

    await store.login('noa@shibutzim.example', 'pw');
    store.logout();

    expect(store.isAuthenticated).toBe(false);
  });
});
