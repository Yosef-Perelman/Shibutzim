import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { makeFakeApi, renderWithStores } from '../../test/renderWithStores';
import { ClockCard } from './ClockCard';

const open = {
  id: 2,
  user_id: 1,
  clock_in: '2026-11-09T05:02:00Z',
  clock_out: null,
  source: 'clock' as const,
  created_by: 1,
  note: null,
};

describe('ClockCard', () => {
  it('offers to clock in and shows the entry once opened', async () => {
    const api = makeFakeApi();
    api.timeEntries.list.mockResolvedValue([]);
    api.timeEntries.clockIn.mockResolvedValue(open);
    await renderWithStores(<ClockCard />, { api });
    await userEvent.click(await screen.findByRole('button', { name: 'Clock in' }));
    expect(await screen.findByText('You are clocked in')).toBeInTheDocument();
    expect(screen.getByText(/Since 07:02/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Clock out' })).toBeInTheDocument();
  });

  it('shows the start time of an entry that is already open and clocks out', async () => {
    const api = makeFakeApi();
    api.timeEntries.list.mockResolvedValue([open]);
    api.timeEntries.clockOut.mockResolvedValue({ ...open, clock_out: '2026-11-09T13:00:00Z' });
    await renderWithStores(<ClockCard />, { api });
    await userEvent.click(await screen.findByRole('button', { name: 'Clock out' }));
    await waitFor(() => expect(screen.getByText('You are not clocked in')).toBeInTheDocument());
  });
});
