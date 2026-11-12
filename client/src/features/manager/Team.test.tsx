import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ApiError } from '../../api/apiClient';
import type { User } from '../../api/types/user';
import { makeUser } from '../../test/fixtures';
import { makeFakeApi, renderWithStores } from '../../test/renderWithStores';
import { Team } from './Team';

const manager = makeUser({
  id: 9,
  name: 'Dana Levi',
  email: 'dana@shibutzim.example',
  role: 'manager',
  hourly_rate: '60.00',
});
const noa = makeUser({ id: 1, name: 'Noa Katz', email: 'noa@shibutzim.example' });
const omer = makeUser({
  id: 2,
  name: 'Omer Barak',
  email: 'omer@shibutzim.example',
  hourly_rate: '38.00',
  is_active: false,
});
const TEAM: User[] = [manager, noa, omer];

async function renderTeam(users: User[] = TEAM) {
  const api = makeFakeApi();
  api.users.list.mockResolvedValue(users);
  const view = await renderWithStores(<Team />, { api, user: manager });
  await screen.findByRole('table', { name: 'Team members' });
  return view;
}

async function fillForm(overrides: Partial<Record<string, string>> = {}) {
  const values = {
    Name: 'Lior Peretz',
    Email: 'lior@shibutzim.example',
    'Hourly rate (₪)': '41.00',
    'Initial password': 'first-password-1',
    ...overrides,
  };
  for (const [label, value] of Object.entries(values)) {
    await userEvent.type(screen.getByLabelText(label, { exact: false }), value ?? '');
  }
}

describe('Team', () => {
  it('lists everyone with role, rate and status', async () => {
    await renderTeam();
    const table = screen.getByRole('table', { name: 'Team members' });
    const noaRow = within(table).getByText('Noa Katz').closest('tr') as HTMLElement;
    expect(within(noaRow).getByText('noa@shibutzim.example')).toBeInTheDocument();
    expect(within(noaRow).getByText('employee')).toBeInTheDocument();
    expect(within(noaRow).getByText('₪42.50')).toBeInTheDocument();
    expect(within(noaRow).getByText('Active')).toBeInTheDocument();
    const omerRow = within(table).getByText('Omer Barak').closest('tr') as HTMLElement;
    expect(within(omerRow).getByText('Inactive')).toBeInTheDocument();
  });

  it('marks the signed-in manager and offers no way to deactivate themself', async () => {
    await renderTeam();
    const table = screen.getByRole('table', { name: 'Team members' });
    const ownRow = within(table).getByText('Dana Levi').closest('tr') as HTMLElement;
    expect(within(ownRow).getByText('You')).toBeInTheDocument();
    expect(within(ownRow).queryByRole('button')).not.toBeInTheDocument();
  });

  it('shows the server message and retries when the team cannot be loaded', async () => {
    const api = makeFakeApi();
    api.users.list.mockRejectedValueOnce(
      new ApiError(403, 'forbidden', 'This action is for managers only.'),
    );
    api.users.list.mockResolvedValueOnce(TEAM);
    await renderWithStores(<Team />, { api, user: manager });
    expect(await screen.findByText('This action is for managers only.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('Noa Katz')).toBeInTheDocument();
  });

  describe('adding a person', () => {
    it('sends the form to the server and lists the new person', async () => {
      const { api } = await renderTeam();
      api.users.create.mockResolvedValue(
        makeUser({ id: 7, name: 'Lior Peretz', email: 'lior@shibutzim.example' }),
      );
      await userEvent.click(screen.getByRole('button', { name: 'Add person' }));
      await fillForm();
      await userEvent.click(
        within(screen.getByRole('dialog')).getByRole('button', { name: 'Add person' }),
      );

      await waitFor(() =>
        expect(api.users.create).toHaveBeenCalledWith({
          name: 'Lior Peretz',
          email: 'lior@shibutzim.example',
          role: 'employee',
          hourly_rate: '41.00',
          password: 'first-password-1',
        }),
      );
      expect(await screen.findByText('Lior Peretz')).toBeInTheDocument();
      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    });

    it('explains every missing or invalid field and sends nothing', async () => {
      const { api } = await renderTeam();
      await userEvent.click(screen.getByRole('button', { name: 'Add person' }));
      await userEvent.click(
        within(screen.getByRole('dialog')).getByRole('button', { name: 'Add person' }),
      );

      expect(await screen.findByText('Enter a name.')).toBeInTheDocument();
      expect(screen.getByText('Enter an email like name@example.com.')).toBeInTheDocument();
      expect(screen.getByText(/Enter a rate above zero/)).toBeInTheDocument();
      expect(screen.getByText('Use at least 8 characters.')).toBeInTheDocument();
      expect(api.users.create).not.toHaveBeenCalled();
    });

    it('rejects a zero rate without sending it', async () => {
      const { api } = await renderTeam();
      await userEvent.click(screen.getByRole('button', { name: 'Add person' }));
      await fillForm({ 'Hourly rate (₪)': '0.00' });
      await userEvent.click(
        within(screen.getByRole('dialog')).getByRole('button', { name: 'Add person' }),
      );

      expect(await screen.findByText(/Enter a rate above zero/)).toBeInTheDocument();
      expect(api.users.create).not.toHaveBeenCalled();
    });

    it('shows a taken email on the email field and keeps the dialog open', async () => {
      const { api } = await renderTeam();
      api.users.create.mockRejectedValue(
        new ApiError(409, 'email_already_used', 'Another person already uses this email.'),
      );
      await userEvent.click(screen.getByRole('button', { name: 'Add person' }));
      await fillForm({ Email: 'noa@shibutzim.example' });
      await userEvent.click(
        within(screen.getByRole('dialog')).getByRole('button', { name: 'Add person' }),
      );

      expect(
        await screen.findByText('Another person already uses this email.'),
      ).toBeInTheDocument();
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByLabelText('Name', { exact: false })).toHaveValue('Lior Peretz');
    });

    it('shows any other server failure inside the dialog', async () => {
      const { api } = await renderTeam();
      api.users.create.mockRejectedValue(
        new ApiError(500, 'internal_error', 'Something went wrong on our side.'),
      );
      await userEvent.click(screen.getByRole('button', { name: 'Add person' }));
      await fillForm();
      await userEvent.click(
        within(screen.getByRole('dialog')).getByRole('button', { name: 'Add person' }),
      );

      expect(await within(screen.getByRole('dialog')).findByRole('alert')).toHaveTextContent(
        'Something went wrong on our side.',
      );
    });
  });

  describe('deactivating and reactivating', () => {
    it('asks first and deactivates after Confirm', async () => {
      const { api } = await renderTeam();
      api.users.setActive.mockResolvedValue({ ...noa, is_active: false });
      await userEvent.click(screen.getByRole('button', { name: 'Deactivate Noa Katz' }));

      const dialog = await screen.findByRole('dialog');
      expect(within(dialog).getByText('Deactivate Noa Katz?')).toBeInTheDocument();
      expect(api.users.setActive).not.toHaveBeenCalled();
      await userEvent.click(within(dialog).getByRole('button', { name: 'Deactivate' }));

      await waitFor(() => expect(api.users.setActive).toHaveBeenCalledWith(1, false));
      const noaRow = screen.getByText('Noa Katz').closest('tr') as HTMLElement;
      await waitFor(() => expect(within(noaRow).getByText('Inactive')).toBeInTheDocument());
      expect(
        within(noaRow).getByRole('button', { name: 'Reactivate Noa Katz' }),
      ).toBeInTheDocument();
    });

    it('changes nothing on Cancel', async () => {
      const { api } = await renderTeam();
      await userEvent.click(screen.getByRole('button', { name: 'Deactivate Noa Katz' }));
      await userEvent.click(
        within(await screen.findByRole('dialog')).getByRole('button', { name: 'Cancel' }),
      );

      expect(api.users.setActive).not.toHaveBeenCalled();
      const noaRow = screen.getByText('Noa Katz').closest('tr') as HTMLElement;
      expect(within(noaRow).getByText('Active')).toBeInTheDocument();
    });

    it('shows the server message in the dialog when the server refuses', async () => {
      const { api } = await renderTeam();
      api.users.setActive.mockRejectedValue(
        new ApiError(404, 'user_not_found', 'User 1 does not exist.'),
      );
      await userEvent.click(screen.getByRole('button', { name: 'Deactivate Noa Katz' }));
      await userEvent.click(
        within(await screen.findByRole('dialog')).getByRole('button', { name: 'Deactivate' }),
      );

      expect(await screen.findByText('User 1 does not exist.')).toBeInTheDocument();
    });

    it('reactivates straight away, without a dialog', async () => {
      const { api } = await renderTeam();
      api.users.setActive.mockResolvedValue({ ...omer, is_active: true });
      await userEvent.click(screen.getByRole('button', { name: 'Reactivate Omer Barak' }));

      await waitFor(() => expect(api.users.setActive).toHaveBeenCalledWith(2, true));
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      const omerRow = screen.getByText('Omer Barak').closest('tr') as HTMLElement;
      await waitFor(() => expect(within(omerRow).getByText('Active')).toBeInTheDocument());
    });
  });
});
