import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../api/apiClient';
import type { Schedule } from '../../api/types/schedule';
import type { Shift } from '../../api/types/shift';
import type { User } from '../../api/types/user';
import { makeUser } from '../../test/fixtures';
import { makeFakeApi, renderWithStores } from '../../test/renderWithStores';
import { ScheduleBoard } from './ScheduleBoard';

const WEEK = '2026-11-15';
const manager = makeUser({ id: 9, name: 'Dana Levi', email: 'dana@x', role: 'manager' });

function employee(id: number, name: string): User {
  return makeUser({ id, name, email: `${name.split(' ')[0]?.toLowerCase()}@x` });
}

const EMPLOYEES = [employee(1, 'Noa Katz'), employee(2, 'Omer Barak')];

const SHIFTS: Shift[] = [
  {
    id: 1,
    template_id: 1,
    name: 'Morning',
    week_start: WEEK,
    starts_at: '2026-11-15T05:00:00Z',
    ends_at: '2026-11-15T13:00:00Z',
    required_staff: 2,
  },
  {
    id: 2,
    template_id: 2,
    name: 'Evening',
    week_start: WEEK,
    starts_at: '2026-11-16T14:00:00Z',
    ends_at: '2026-11-16T21:00:00Z',
    required_staff: 1,
  },
];

function schedule(status: 'draft' | 'published'): Schedule {
  return {
    id: 5,
    week_start: WEEK,
    status,
    published_at: status === 'published' ? '2026-11-10T08:00:00Z' : null,
    shifts: [
      {
        shift_id: 1,
        name: 'Morning',
        starts_at: '2026-11-15T05:00:00Z',
        ends_at: '2026-11-15T13:00:00Z',
        required_staff: 2,
        assigned_count: 1,
        unfilled_count: 1,
      },
      {
        shift_id: 2,
        name: 'Evening',
        starts_at: '2026-11-16T14:00:00Z',
        ends_at: '2026-11-16T21:00:00Z',
        required_staff: 1,
        assigned_count: 1,
        unfilled_count: 0,
      },
    ],
    assignments: [
      { id: 11, shift_id: 1, user_id: 1, user_name: 'Noa Katz', starts_at: '', ends_at: '' },
      { id: 12, shift_id: 2, user_id: 2, user_name: 'Omer Barak', starts_at: '', ends_at: '' },
    ],
  };
}

function boardApi(options: { shifts?: Shift[]; schedule?: Schedule | null } = {}) {
  const api = makeFakeApi();
  api.shifts.list.mockResolvedValue(options.shifts ?? SHIFTS);
  api.users.list.mockResolvedValue(EMPLOYEES);
  if (options.schedule) api.schedules.get.mockResolvedValue(options.schedule);
  else api.schedules.get.mockRejectedValue(new ApiError(404, 'schedule_not_found', 'None.'));
  return api;
}

beforeEach(() => {
  // Monday 9 Nov 2026: the board opens on the week of Sunday 15 Nov.
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-11-09T12:00:00Z'));
});

afterEach(() => {
  vi.useRealTimers();
});

describe('ScheduleBoard with no shifts', () => {
  it("offers to create the week's shifts", async () => {
    const api = boardApi({ shifts: [] });
    api.shifts.generate.mockResolvedValue({ week_start: WEEK, created: 2, shifts: SHIFTS });
    await renderWithStores(<ScheduleBoard />, { api, user: manager });
    await userEvent.click(await screen.findByRole('button', { name: "Create this week's shifts" }));
    await waitFor(() => expect(api.shifts.generate).toHaveBeenCalledWith(WEEK));
  });
});

describe('ScheduleBoard with shifts but no schedule', () => {
  it('shows every shift of the week with nobody assigned and a "No schedule" badge', async () => {
    await renderWithStores(<ScheduleBoard />, { api: boardApi(), user: manager });
    const sunday = await screen.findByRole('region', { name: 'Sun 15 Nov' });
    expect(within(sunday).getByText('Morning')).toBeInTheDocument();
    expect(within(sunday).getByText('0 / 2')).toBeInTheDocument();
    expect(screen.getByText('No schedule')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Publish' })).not.toBeInTheDocument();
  });

  it("shows the solver's sentences for the shifts it could not fill after Generate", async () => {
    const api = boardApi();
    api.schedules.generate.mockResolvedValue({
      schedule: schedule('draft'),
      unfilled: [
        {
          shift_id: 1,
          required: 2,
          assigned: 1,
          missing: 1,
          reasons: [],
          sentence: 'Sunday 07:00 needs 2, only 1 available; Dana excluded by minimum rest',
        },
      ],
      score: { filled: 2, preferred: 0, spread_minutes: 0, value: 0 },
      complete: true,
      steps: 5,
    });
    await renderWithStores(<ScheduleBoard />, { api, user: manager });
    await userEvent.click(await screen.findByRole('button', { name: 'Generate' }));
    const panel = await screen.findByRole('region', { name: 'Last generate' });
    expect(
      within(panel).getByText(
        'Sunday 07:00 needs 2, only 1 available; Dana excluded by minimum rest',
      ),
    ).toBeInTheDocument();
    expect(await screen.findByText('Draft')).toBeInTheDocument();
  });
});

describe('ScheduleBoard with a draft', () => {
  it('asks before replacing a draft that already has people on it', async () => {
    const api = boardApi({ schedule: schedule('draft') });
    api.schedules.generate.mockResolvedValue({
      schedule: schedule('draft'),
      unfilled: [],
      score: { filled: 2, preferred: 0, spread_minutes: 0, value: 0 },
      complete: true,
      steps: 1,
    });
    await renderWithStores(<ScheduleBoard />, { api, user: manager });
    await userEvent.click(await screen.findByRole('button', { name: 'Generate' }));
    expect(api.schedules.generate).not.toHaveBeenCalled();
    const dialog = await screen.findByRole('dialog', { name: 'Replace the current draft?' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Generate' }));
    await waitFor(() => expect(api.schedules.generate).toHaveBeenCalledTimes(1));
  });

  it('keeps the dialog open and shows the server message when an edit is blocked', async () => {
    const api = boardApi({ schedule: schedule('draft') });
    api.schedules.addAssignment.mockRejectedValue(
      new ApiError(409, 'min_rest_violation', 'Omer needs 8 hours of rest between shifts.'),
    );
    await renderWithStores(<ScheduleBoard />, { api, user: manager });
    await userEvent.click(
      await screen.findByRole('button', { name: 'Add someone to Morning on Sun 15 Nov' }),
    );
    const dialog = await screen.findByRole('dialog', { name: 'Add someone' });
    await userEvent.click(within(dialog).getByRole('combobox', { name: 'Employee' }));
    await userEvent.click(await screen.findByRole('option', { name: 'Omer Barak' }));
    await userEvent.click(within(dialog).getByRole('button', { name: 'Add' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'Omer needs 8 hours of rest between shifts.',
    );
    expect(api.schedules.addAssignment).toHaveBeenCalledWith(WEEK, { shift_id: 1, user_id: 2 });
  });

  it('does not offer someone who is already on the shift', async () => {
    await renderWithStores(<ScheduleBoard />, {
      api: boardApi({ schedule: schedule('draft') }),
      user: manager,
    });
    await userEvent.click(
      await screen.findByRole('button', { name: 'Add someone to Morning on Sun 15 Nov' }),
    );
    const dialog = await screen.findByRole('dialog', { name: 'Add someone' });
    await userEvent.click(within(dialog).getByRole('combobox', { name: 'Employee' }));
    expect(await screen.findByRole('option', { name: 'Omer Barak' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Noa Katz' })).not.toBeInTheDocument();
  });

  it('removes an assignment only after confirmation', async () => {
    const api = boardApi({ schedule: schedule('draft') });
    api.schedules.removeAssignment.mockResolvedValue(undefined);
    await renderWithStores(<ScheduleBoard />, { api, user: manager });
    await userEvent.click(await screen.findByRole('button', { name: 'Actions for Noa Katz' }));
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Remove' }));
    expect(api.schedules.removeAssignment).not.toHaveBeenCalled();
    const dialog = await screen.findByRole('dialog', { name: 'Remove from the shift?' });
    expect(
      within(dialog).getByText(/Remove Noa Katz from Morning on Sun 15 Nov/),
    ).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Remove' }));
    await waitFor(() => expect(api.schedules.removeAssignment).toHaveBeenCalledWith(WEEK, 11));
  });

  it('publishes after confirmation and then turns Generate off', async () => {
    const api = boardApi({ schedule: schedule('draft') });
    api.schedules.publish.mockResolvedValue(schedule('published'));
    await renderWithStores(<ScheduleBoard />, { api, user: manager });
    await userEvent.click(await screen.findByRole('button', { name: 'Publish' }));
    const dialog = await screen.findByRole('dialog', { name: 'Publish the schedule?' });
    expect(within(dialog).getByText(/Employees will see it immediately/)).toBeInTheDocument();
    expect(api.schedules.publish).not.toHaveBeenCalled();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Publish' }));
    await waitFor(() => expect(api.schedules.publish).toHaveBeenCalledWith(WEEK));
    expect(await screen.findByText('Published')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Generate' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Publish' })).not.toBeInTheDocument();
  });
});

describe('ScheduleBoard errors', () => {
  it('shows the server message with a retry when the week cannot be loaded', async () => {
    const api = boardApi();
    api.shifts.list.mockRejectedValueOnce(
      new ApiError(500, 'internal_error', 'Something went wrong on our side.'),
    );
    await renderWithStores(<ScheduleBoard />, { api, user: manager });
    expect(await screen.findByText('Something went wrong on our side.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByRole('region', { name: 'Sun 15 Nov' })).toBeInTheDocument();
  });
});
