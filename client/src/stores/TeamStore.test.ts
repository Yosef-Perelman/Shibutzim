import { describe, expect, it, vi } from 'vitest';

import { ApiError } from '../api/apiClient';
import type { NewUser } from '../api/types/user';
import { makeUser } from '../test/fixtures';
import { TeamStore } from './TeamStore';

const NEW_PERSON: NewUser = {
  email: 'lior@shibutzim.example',
  name: 'Lior Peretz',
  role: 'employee',
  hourly_rate: '41.00',
  password: 'first-password-1',
};

function setup() {
  const api = { users: { list: vi.fn(), create: vi.fn(), setActive: vi.fn() } };
  return { api, store: new TeamStore({ api }) };
}

describe('TeamStore', () => {
  it('loads everyone, active or not, ordered by name', async () => {
    const { api, store } = setup();
    api.users.list.mockResolvedValue([
      makeUser({ id: 2, name: 'Omer Barak' }),
      makeUser({ id: 1, name: 'Noa Katz', is_active: false }),
    ]);

    await store.load();

    expect(api.users.list).toHaveBeenCalledWith();
    expect(store.status).toBe('loaded');
    expect(store.people.map((person) => person.name)).toEqual(['Noa Katz', 'Omer Barak']);
  });

  it("keeps the server's message when the list cannot be loaded", async () => {
    const { api, store } = setup();
    api.users.list.mockRejectedValue(
      new ApiError(403, 'forbidden', 'This action is for managers only.'),
    );

    await store.load();

    expect(store.status).toBe('error');
    expect(store.error).toBe('This action is for managers only.');
  });

  it('adds the created person to the list in name order', async () => {
    const { api, store } = setup();
    api.users.list.mockResolvedValue([makeUser({ id: 1, name: 'Noa Katz' })]);
    await store.load();
    api.users.create.mockResolvedValue(makeUser({ id: 7, name: 'Lior Peretz' }));

    const result = await store.addPerson(NEW_PERSON);

    expect(api.users.create).toHaveBeenCalledWith(NEW_PERSON);
    expect(result.ok).toBe(true);
    expect(store.people.map((person) => person.name)).toEqual(['Lior Peretz', 'Noa Katz']);
  });

  it('returns the code and message when the email is taken, and adds nobody', async () => {
    const { api, store } = setup();
    api.users.list.mockResolvedValue([makeUser({ id: 1 })]);
    await store.load();
    api.users.create.mockRejectedValue(
      new ApiError(409, 'email_already_used', 'Another person already uses this email.'),
    );

    const result = await store.addPerson(NEW_PERSON);

    expect(result).toEqual({
      ok: false,
      code: 'email_already_used',
      message: 'Another person already uses this email.',
    });
    expect(store.people).toHaveLength(1);
  });

  it('replaces the person with the server’s answer when deactivating', async () => {
    const { api, store } = setup();
    const noa = makeUser({ id: 1, name: 'Noa Katz' });
    api.users.list.mockResolvedValue([noa]);
    await store.load();
    api.users.setActive.mockResolvedValue({ ...noa, is_active: false });

    const result = await store.setActive(noa, false);

    expect(api.users.setActive).toHaveBeenCalledWith(1, false);
    expect(result.ok).toBe(true);
    expect(store.people[0]?.is_active).toBe(false);
  });

  it('leaves the person as they were when the server refuses', async () => {
    const { api, store } = setup();
    const dana = makeUser({ id: 9, name: 'Dana Levi', role: 'manager' });
    api.users.list.mockResolvedValue([dana]);
    await store.load();
    api.users.setActive.mockRejectedValue(
      new ApiError(422, 'cannot_deactivate_self', 'You cannot deactivate your own account.'),
    );

    const result = await store.setActive(dana, false);

    expect(result).toEqual({
      ok: false,
      code: 'cannot_deactivate_self',
      message: 'You cannot deactivate your own account.',
    });
    expect(store.people[0]?.is_active).toBe(true);
  });

  it('shows the newest answer when the list is loaded twice quickly', async () => {
    const { api, store } = setup();
    let resolveFirst: (users: unknown[]) => void = () => undefined;
    api.users.list.mockReturnValueOnce(new Promise((resolve) => (resolveFirst = resolve)));
    api.users.list.mockResolvedValueOnce([makeUser({ id: 2, name: 'Newer Answer' })]);

    const first = store.load();
    await store.load();
    resolveFirst([makeUser({ id: 1, name: 'Older Answer' })]);
    await first;

    expect(store.people.map((person) => person.name)).toEqual(['Newer Answer']);
  });
});
