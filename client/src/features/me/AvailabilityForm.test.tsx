import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ApiError } from '../../api/apiClient';
import { makeFakeApi, renderWithStores } from '../../test/renderWithStores';
import { AvailabilityForm } from './AvailabilityForm';

function shiftsFor(week: string) {
  return [
    {
      id: 1,
      template_id: 1,
      name: 'Morning',
      week_start: week,
      starts_at: '2026-11-15T05:00:00Z',
      ends_at: '2026-11-15T13:00:00Z',
      required_staff: 2,
    },
    {
      id: 2,
      template_id: 2,
      name: 'Evening',
      week_start: week,
      starts_at: '2026-11-15T14:00:00Z',
      ends_at: '2026-11-15T21:00:00Z',
      required_staff: 2,
    },
  ];
}

function openApi(scheduleExists = false) {
  const api = makeFakeApi();
  api.shifts.list.mockResolvedValue(shiftsFor('2026-11-15'));
  api.availabilities.list.mockResolvedValue([]);
  if (scheduleExists) api.schedules.get.mockResolvedValue({ id: 1 });
  else api.schedules.get.mockRejectedValue(new ApiError(404, 'schedule_not_found', 'None.'));
  return api;
}

describe('AvailabilityForm', () => {
  it('shows one three-state control per shift and saves the week in one request', async () => {
    const api = openApi();
    api.availabilities.set.mockResolvedValue([
      { id: 1, shift_id: 1, user_id: 1, status: 'preferred' },
    ]);
    await renderWithStores(<AvailabilityForm />, { api });
    const morning = await screen.findByRole('radiogroup', { name: /07:00 Morning/ });
    const save = screen.getByRole('button', { name: 'Save availability' });
    expect(save).toBeDisabled();

    const preferred = morning.querySelector('input[value="preferred"]');
    expect(preferred).not.toBeNull();
    await userEvent.click(preferred as Element);
    expect(save).toBeEnabled();

    await userEvent.click(save);
    await waitFor(() => expect(api.availabilities.set).toHaveBeenCalledTimes(1));
    expect(api.availabilities.set).toHaveBeenCalledWith(
      expect.objectContaining({ items: [{ shift_id: 1, status: 'preferred' }] }),
    );
    await waitFor(() => expect(save).toBeDisabled());
  });

  it('explains that a shift with no answer counts as available', async () => {
    await renderWithStores(<AvailabilityForm />, { api: openApi() });
    expect(
      await screen.findByText(
        'Choose when you can work. A shift you do not answer counts as available; mark the ones you cannot work.',
      ),
    ).toBeInTheDocument();
  });

  it('shows an unanswered shift as available', async () => {
    await renderWithStores(<AvailabilityForm />, { api: openApi() });
    const morning = await screen.findByRole('radiogroup', { name: /07:00 Morning/ });
    const evening = screen.getByRole('radiogroup', { name: /16:00 Evening/ });
    for (const group of [morning, evening]) {
      expect(group.querySelector('input[value="available"]')).toBeChecked();
      expect(group.querySelector('input[value="unavailable"]')).not.toBeChecked();
    }
  });

  it('keeps Save disabled when available is chosen for an unanswered shift', async () => {
    await renderWithStores(<AvailabilityForm />, { api: openApi() });
    const morning = await screen.findByRole('radiogroup', { name: /07:00 Morning/ });
    await userEvent.click(morning.querySelector('input[value="available"]') as Element);
    expect(screen.getByRole('button', { name: 'Save availability' })).toBeDisabled();
  });

  it('enables Save for unavailable on an unanswered shift and sends that row', async () => {
    const api = openApi();
    api.availabilities.set.mockResolvedValue([
      { id: 1, shift_id: 1, user_id: 1, status: 'unavailable' },
    ]);
    await renderWithStores(<AvailabilityForm />, { api });
    const morning = await screen.findByRole('radiogroup', { name: /07:00 Morning/ });
    const save = screen.getByRole('button', { name: 'Save availability' });
    expect(save).toBeDisabled();

    await userEvent.click(morning.querySelector('input[value="unavailable"]') as Element);
    expect(save).toBeEnabled();

    await userEvent.click(save);
    await waitFor(() => expect(api.availabilities.set).toHaveBeenCalledTimes(1));
    expect(api.availabilities.set).toHaveBeenCalledWith(
      expect.objectContaining({ items: [{ shift_id: 1, status: 'unavailable' }] }),
    );
    await waitFor(() => expect(save).toBeDisabled());
  });

  it('is read-only with an explanation once the week has a schedule', async () => {
    await renderWithStores(<AvailabilityForm />, { api: openApi(true) });
    expect(await screen.findByText(/schedule for this week already exists/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save availability' })).not.toBeInTheDocument();
    const radios = screen.getAllByRole('radio');
    expect(radios.every((radio) => (radio as HTMLInputElement).disabled)).toBe(true);
  });

  it('says so when the week has no shifts yet', async () => {
    const api = openApi();
    api.shifts.list.mockResolvedValue([]);
    await renderWithStores(<AvailabilityForm />, { api });
    expect(await screen.findByText('No shifts for this week yet')).toBeInTheDocument();
  });

  it('shows the server message when saving fails and keeps the changes', async () => {
    const api = openApi();
    api.availabilities.set.mockRejectedValue(
      new ApiError(500, 'internal_error', 'Something went wrong on our side.'),
    );
    await renderWithStores(<AvailabilityForm />, { api });
    const morning = await screen.findByRole('radiogroup', { name: /07:00 Morning/ });
    await userEvent.click(morning.querySelector('input[value="unavailable"]') as Element);
    await userEvent.click(screen.getByRole('button', { name: 'Save availability' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong on our side.');
    expect(screen.getByRole('button', { name: 'Save availability' })).toBeEnabled();
  });
});
