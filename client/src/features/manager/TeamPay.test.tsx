import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ApiError } from '../../api/apiClient';
import type { Pay, TeamPay as TeamPayDto } from '../../api/types/pay';
import { makeUser } from '../../test/fixtures';
import { makeFakeApi, renderWithStores } from '../../test/renderWithStores';
import { TeamPay } from './TeamPay';

const manager = makeUser({ id: 9, name: 'Dana Levi', email: 'dana@x', role: 'manager' });

const team: TeamPayDto = {
  from: '2026-11-01',
  to: '2026-11-30',
  seconds: 0,
  hours: '27.50',
  amount: '1213.50',
  users: [
    {
      user_id: 1,
      name: 'Noa Katz',
      role: 'employee',
      hourly_rate: '42.50',
      seconds: 0,
      hours: '17.50',
      amount: '743.75',
      open_entries: 0,
    },
    {
      user_id: 2,
      name: 'Omer Barak',
      role: 'employee',
      hourly_rate: '38.00',
      seconds: 0,
      hours: '10.00',
      amount: '469.75',
      open_entries: 2,
    },
  ],
};

const noaPay: Pay = {
  user_id: 1,
  from: '2026-11-01',
  to: '2026-11-30',
  seconds: 0,
  hours: '17.50',
  amount: '743.75',
  open_entries: 0,
  days: [
    {
      work_day: '2026-11-08',
      seconds: 0,
      hours: '8.00',
      amount: '340.00',
      lines: [
        {
          from_hour: '0',
          to_hour: '8',
          multiplier: '1.00',
          seconds: 28800,
          hours: '8.00',
          amount: '340.00',
        },
      ],
    },
  ],
};

describe('TeamPay', () => {
  it("lists every user with the server's hours and amounts, and the totals", async () => {
    const api = makeFakeApi();
    api.pay.team.mockResolvedValue(team);
    await renderWithStores(<TeamPay />, { api, user: manager });
    const table = await screen.findByRole('table', { name: 'Team pay for November 2026' });
    expect(within(table).getByText('Noa Katz')).toBeInTheDocument();
    expect(within(table).getByText('₪743.75')).toBeInTheDocument();
    expect(within(table).getByText('₪42.50')).toBeInTheDocument();
    expect(within(table).getByText('2 open')).toBeInTheDocument();
    expect(within(table).getByText('₪1,213.50')).toBeInTheDocument();
    expect(within(table).getByText('27.50 h')).toBeInTheDocument();
  });

  it("opens one person's breakdown with the shared component", async () => {
    const api = makeFakeApi();
    api.pay.team.mockResolvedValue(team);
    api.pay.get.mockResolvedValue(noaPay);
    await renderWithStores(<TeamPay />, { api, user: manager });
    await userEvent.click(
      await screen.findByRole('button', { name: 'Show the pay breakdown of Noa Katz' }),
    );
    await waitFor(() =>
      expect(api.pay.get).toHaveBeenCalledWith({ from: '2026-11-01', to: '2026-11-30' }, 1),
    );
    const drawer = await screen.findByRole('dialog');
    expect(await within(drawer).findByRole('region', { name: 'Sun 8 Nov' })).toBeInTheDocument();
    expect(within(drawer).getByText('0–8 h · ×1.00')).toBeInTheDocument();
  });

  it('shows the server message and retries when the team cannot be loaded', async () => {
    const api = makeFakeApi();
    api.pay.team.mockRejectedValueOnce(
      new ApiError(403, 'forbidden', 'This action is for managers only.'),
    );
    api.pay.team.mockResolvedValueOnce(team);
    await renderWithStores(<TeamPay />, { api, user: manager });
    expect(await screen.findByText('This action is for managers only.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('Noa Katz')).toBeInTheDocument();
  });

  it('says so when nobody has entries in the month', async () => {
    const api = makeFakeApi();
    api.pay.team.mockResolvedValue({ ...team, users: [], hours: '0.00', amount: '0.00' });
    await renderWithStores(<TeamPay />, { api, user: manager });
    expect(await screen.findByText('No one to show')).toBeInTheDocument();
  });
});
