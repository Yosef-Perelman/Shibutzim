import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ApiError } from '../../api/apiClient';
import type { Pay } from '../../api/types/pay';
import { makeFakeApi, renderWithStores } from '../../test/renderWithStores';
import { MyPay } from './MyPay';

const pay: Pay = {
  user_id: 1,
  from: '2026-11-01',
  to: '2026-11-30',
  seconds: 0,
  hours: '19.00',
  amount: '1213.50',
  open_entries: 0,
  days: [
    {
      work_day: '2026-11-08',
      seconds: 36000,
      hours: '10.00',
      amount: '482.50',
      lines: [
        {
          from_hour: '0',
          to_hour: '8',
          multiplier: '1.00',
          seconds: 28800,
          hours: '8.00',
          amount: '340.00',
        },
        {
          from_hour: '8',
          to_hour: '10',
          multiplier: '1.25',
          seconds: 7200,
          hours: '2.00',
          amount: '106.25',
        },
        {
          from_hour: '10',
          to_hour: null,
          multiplier: '1.50',
          seconds: 0,
          hours: '0.00',
          amount: '0.00',
        },
      ],
    },
  ],
};

describe('MyPay', () => {
  it('shows the month total with the shekel sign and each day with its tier lines', async () => {
    const api = makeFakeApi();
    api.pay.get.mockResolvedValue(pay);
    await renderWithStores(<MyPay />, { api });
    expect(await screen.findByText('₪1,213.50')).toBeInTheDocument();
    expect(screen.getByText('19.00 h')).toBeInTheDocument();
    const day = screen.getByRole('region', { name: 'Sun 8 Nov' });
    expect(within(day).getByText('₪482.50')).toBeInTheDocument();
    expect(within(day).getByText('0–8 h · ×1.00')).toBeInTheDocument();
    expect(within(day).getByText('8–10 h · ×1.25')).toBeInTheDocument();
    // A tier with no hours that day is not listed.
    expect(within(day).queryByText(/10\+ h/)).not.toBeInTheDocument();
  });

  it('warns about open entries', async () => {
    const api = makeFakeApi();
    api.pay.get.mockResolvedValue({ ...pay, open_entries: 1 });
    await renderWithStores(<MyPay />, { api });
    expect(await screen.findByText(/1 time entry has no clock-out yet/)).toBeInTheDocument();
  });

  it('says so when the month has no entries', async () => {
    const api = makeFakeApi();
    api.pay.get.mockResolvedValue({ ...pay, days: [], amount: '0.00', hours: '0.00' });
    await renderWithStores(<MyPay />, { api });
    expect(await screen.findByText('No pay yet this month')).toBeInTheDocument();
  });

  it('shows the server message and retries', async () => {
    const api = makeFakeApi();
    api.pay.get.mockRejectedValueOnce(
      new ApiError(500, 'internal_error', 'Something went wrong on our side.'),
    );
    api.pay.get.mockResolvedValueOnce(pay);
    await renderWithStores(<MyPay />, { api });
    expect(await screen.findByText('Something went wrong on our side.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('₪1,213.50')).toBeInTheDocument();
  });

  it('loads the previous month when the arrow is pressed', async () => {
    const api = makeFakeApi();
    api.pay.get.mockResolvedValue(pay);
    await renderWithStores(<MyPay />, { api });
    await screen.findByText('₪1,213.50');
    api.pay.get.mockClear();
    await userEvent.click(screen.getByRole('button', { name: 'Previous month' }));
    expect(api.pay.get).toHaveBeenCalledTimes(1);
  });
});
