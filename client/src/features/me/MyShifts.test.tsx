import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ApiError } from '../../api/apiClient';
import type { Schedule } from '../../api/types/schedule';
import { makeFakeApi, renderWithStores } from '../../test/renderWithStores';
import { MyShifts } from './MyShifts';

const schedule: Schedule = {
  id: 1,
  week_start: '2026-11-08',
  status: 'published',
  published_at: '2026-11-05T08:00:00Z',
  shifts: [
    {
      shift_id: 1,
      name: 'Morning',
      starts_at: '2026-11-08T05:00:00Z',
      ends_at: '2026-11-08T13:00:00Z',
      required_staff: 2,
      assigned_count: 2,
      unfilled_count: 0,
    },
    {
      shift_id: 2,
      name: 'Evening',
      starts_at: '2026-11-08T14:00:00Z',
      ends_at: '2026-11-08T21:00:00Z',
      required_staff: 1,
      assigned_count: 1,
      unfilled_count: 0,
    },
  ],
  assignments: [
    { id: 1, shift_id: 1, user_id: 1, user_name: 'Noa Katz', starts_at: '', ends_at: '' },
    { id: 2, shift_id: 1, user_id: 7, user_name: 'Omer Barak', starts_at: '', ends_at: '' },
    { id: 3, shift_id: 2, user_id: 7, user_name: 'Omer Barak', starts_at: '', ends_at: '' },
  ],
};

describe('MyShifts', () => {
  it('lists own shifts first and the whole team below', async () => {
    const api = makeFakeApi();
    api.schedules.get.mockResolvedValue(schedule);
    await renderWithStores(<MyShifts />, { api });
    const own = await screen.findByRole('region', { name: 'Your shifts' });
    expect(within(own).getByText(/Morning/)).toBeInTheDocument();
    expect(within(own).getByText('07:00–15:00')).toBeInTheDocument();
    expect(within(own).queryByText(/Evening/)).not.toBeInTheDocument();
    const team = screen.getByRole('region', { name: 'Whole team' });
    expect(within(team).getByText('Evening')).toBeInTheDocument();
    expect(within(team).getByText('You, Omer Barak')).toBeInTheDocument();
  });

  it('says so when the week has no published schedule', async () => {
    const api = makeFakeApi();
    api.schedules.get.mockRejectedValue(new ApiError(404, 'schedule_not_found', 'None.'));
    await renderWithStores(<MyShifts />, { api });
    expect(await screen.findByText('Schedule not published yet')).toBeInTheDocument();
  });

  it('shows the server message and retries', async () => {
    const api = makeFakeApi();
    api.schedules.get.mockRejectedValueOnce(
      new ApiError(500, 'internal_error', 'Something went wrong on our side.'),
    );
    api.schedules.get.mockResolvedValueOnce(schedule);
    await renderWithStores(<MyShifts />, { api });
    expect(await screen.findByText('Something went wrong on our side.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByRole('region', { name: 'Your shifts' })).toBeInTheDocument();
  });

  it('loads the next week when the arrow is pressed', async () => {
    const api = makeFakeApi();
    api.schedules.get.mockResolvedValue(schedule);
    await renderWithStores(<MyShifts />, { api });
    await screen.findByRole('region', { name: 'Your shifts' });
    api.schedules.get.mockClear();
    await userEvent.click(screen.getByRole('button', { name: 'Next week' }));
    expect(api.schedules.get).toHaveBeenCalledTimes(1);
  });
});
