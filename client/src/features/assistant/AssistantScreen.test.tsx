import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ApiError } from '../../api/apiClient';
import type { ChatOut, ScheduleProposal } from '../../api/types/assistant';
import { makeUser } from '../../test/fixtures';
import { makeFakeApi, renderWithStores } from '../../test/renderWithStores';
import { AssistantScreen } from './AssistantScreen';

const manager = makeUser({ id: 9, name: 'Dana Levi', role: 'manager' });

function answer(overrides: Partial<ChatOut> = {}): ChatOut {
  return {
    message: 'You worked 8 hours.',
    citations: [],
    tool_calls: [],
    proposal: null,
    ...overrides,
  };
}

const proposal: ScheduleProposal = {
  type: 'schedule_draft',
  week_start: '2026-11-15',
  unavailable: [{ user_id: 3, name: 'Noa Katz', day: '2026-11-17' }],
  summary: '20 of 21 positions filled. 1 shift is short of staff.',
  filled: 20,
  required: 21,
  replaces_draft: false,
  assignments: [
    {
      shift_id: 1,
      date: '2026-11-15',
      weekday: 'Sunday',
      name: 'Morning',
      start: '07:00',
      end: '15:00',
      people: ['Omer Barak', 'Tamar Mizrahi'],
    },
  ],
  unfilled: ['Tuesday 07:00 needs 2, only 1 available'],
};

async function open(user = makeUser()) {
  const api = makeFakeApi();
  const view = await renderWithStores(<AssistantScreen />, { user, api });
  return { ...view, api, typist: userEvent.setup() };
}

async function ask(typist: ReturnType<typeof userEvent.setup>, text: string) {
  await typist.type(screen.getByRole('textbox', { name: 'Your question' }), text);
  await typist.click(screen.getByRole('button', { name: 'Send' }));
}

describe('AssistantScreen when empty', () => {
  it('explains what an employee can ask and offers example questions', async () => {
    await open();

    expect(screen.getByRole('heading', { name: 'Assistant' })).toBeInTheDocument();
    expect(screen.getByText('Ask about your work')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'How many hours did I work this month?' }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Build next week/ })).not.toBeInTheDocument();
  });

  it('offers a manager manager questions', async () => {
    await open(manager);

    expect(screen.getByRole('button', { name: "Build next week's schedule" })).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'How many hours did I work this month?' }),
    ).not.toBeInTheDocument();
  });

  it('sends an example question when it is pressed', async () => {
    const { api, typist } = await open();
    api.assistant.chat.mockResolvedValue(answer());

    await typist.click(
      screen.getByRole('button', { name: 'How many hours did I work this month?' }),
    );

    expect(api.assistant.chat).toHaveBeenCalledWith([
      { role: 'user', content: 'How many hours did I work this month?' },
    ]);
  });
});

describe('AssistantScreen conversation', () => {
  it('shows the question and the answer and clears the box', async () => {
    const { api, typist } = await open();
    api.assistant.chat.mockResolvedValue(answer());

    await ask(typist, 'How many hours?');

    expect(await screen.findByText('You worked 8 hours.')).toBeInTheDocument();
    expect(screen.getByText('How many hours?')).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Your question' })).toHaveValue('');
    expect(screen.queryByText('Ask about your work')).not.toBeInTheDocument();
  });

  it('sends with Enter', async () => {
    const { api, typist } = await open();
    api.assistant.chat.mockResolvedValue(answer());

    await typist.type(screen.getByRole('textbox', { name: 'Your question' }), 'hello{Enter}');

    expect(api.assistant.chat).toHaveBeenCalledTimes(1);
  });

  it('keeps Shift+Enter for a new line', async () => {
    const { api, typist } = await open();

    await typist.type(
      screen.getByRole('textbox', { name: 'Your question' }),
      'a{Shift>}{Enter}{/Shift}b',
    );

    expect(api.assistant.chat).not.toHaveBeenCalled();
    expect(screen.getByRole('textbox', { name: 'Your question' })).toHaveValue('a\nb');
  });

  it('does not send an empty question', async () => {
    const { api, typist } = await open();

    await typist.click(screen.getByRole('button', { name: 'Send' }));

    expect(api.assistant.chat).not.toHaveBeenCalled();
  });

  it('says it is thinking and blocks a second question while it waits', async () => {
    const { api, typist } = await open();
    let finish: (value: ChatOut) => void = () => undefined;
    api.assistant.chat.mockReturnValue(new Promise((resolve) => (finish = resolve)));

    await ask(typist, 'hello');

    expect(screen.getByRole('status')).toHaveTextContent('Thinking');
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled();
    finish(answer());
    await screen.findByText('You worked 8 hours.');
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('names the handbook section the answer used and what was looked at', async () => {
    const { api, typist } = await open();
    api.assistant.chat.mockResolvedValue(
      answer({
        message: 'According to the Shift swaps section, ask your manager.',
        citations: ['Shift swaps'],
        tool_calls: [
          { name: 'search_policy', args: { query: 'swap' } },
          { name: 'get_my_hours', args: {} },
        ],
      }),
    );

    await ask(typist, 'Can I swap?');

    expect(await screen.findByText('Handbook: Shift swaps')).toBeInTheDocument();
    expect(screen.getByText('Looked at: the handbook, your hours')).toBeInTheDocument();
  });

  it('starts over with New conversation', async () => {
    const { api, typist } = await open();
    api.assistant.chat.mockResolvedValue(answer());
    await ask(typist, 'hi');
    await screen.findByText('You worked 8 hours.');

    await typist.click(screen.getByRole('button', { name: 'New conversation' }));

    expect(screen.getByText('Ask about your work')).toBeInTheDocument();
    expect(screen.queryByText('You worked 8 hours.')).not.toBeInTheDocument();
  });
});

describe('AssistantScreen errors', () => {
  it('shows the server message with a Retry that asks again', async () => {
    const { api, typist } = await open();
    api.assistant.chat.mockRejectedValueOnce(
      new ApiError(500, 'internal_error', 'Something went wrong on our side.'),
    );
    await ask(typist, 'hi');

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong on our side.');
    api.assistant.chat.mockResolvedValue(answer());
    await typist.click(screen.getByRole('button', { name: 'Retry' }));

    expect(await screen.findByText('You worked 8 hours.')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('says the assistant is not available when the server says so', async () => {
    const { api, typist } = await open();
    api.assistant.chat.mockRejectedValue(
      new ApiError(503, 'assistant_unavailable', 'The assistant is not available right now.'),
    );

    await ask(typist, 'hi');

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The assistant is not available right now.',
    );
  });
});

describe('AssistantScreen proposals', () => {
  async function withProposal(overrides: Partial<ScheduleProposal> = {}) {
    const ctx = await open(manager);
    ctx.api.assistant.chat.mockResolvedValue(
      answer({ message: 'I prepared a proposal.', proposal: { ...proposal, ...overrides } }),
    );
    await ask(ctx.typist, "Build next week's schedule. Noa can't work Tuesday.");
    await screen.findByText('I prepared a proposal.');
    return ctx;
  }

  it('shows the proposal with its summary, days off and what is still short', async () => {
    await withProposal();

    expect(
      screen.getByRole('heading', { name: 'Proposed schedule for 15–21 Nov' }),
    ).toBeInTheDocument();
    expect(
      screen.getByText('20 of 21 positions filled. 1 shift is short of staff.'),
    ).toBeInTheDocument();
    expect(screen.getByText('Noa Katz is off Tue 17 Nov')).toBeInTheDocument();
    expect(screen.getByText('Tuesday 07:00 needs 2, only 1 available')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
  });

  it('lists the proposed shifts with their people when asked', async () => {
    const { typist } = await withProposal();

    await typist.click(screen.getByRole('button', { name: 'Show shifts' }));

    expect(screen.getByText('Sun 15 Nov · Morning 07:00–15:00')).toBeInTheDocument();
    expect(screen.getByText('Omer Barak, Tamar Mizrahi')).toBeInTheDocument();
  });

  it('warns that confirming replaces the current draft', async () => {
    await withProposal({ replaces_draft: true });

    expect(
      screen.getByText('Confirming replaces the current draft of that week.'),
    ).toBeInTheDocument();
  });

  it('confirming creates the draft through the normal endpoint and links to the board', async () => {
    const { api, typist } = await withProposal();
    api.schedules.generate.mockResolvedValue({});

    await typist.click(screen.getByRole('button', { name: 'Confirm' }));

    expect(api.schedules.generate).toHaveBeenCalledWith('2026-11-15', {
      unavailable: [{ user_id: 3, day: '2026-11-17' }],
    });
    expect(await screen.findByText('Draft created')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open schedule' })).toHaveAttribute(
      'href',
      '/manager/schedule',
    );
    expect(screen.queryByRole('button', { name: 'Confirm' })).not.toBeInTheDocument();
  });

  it("shows the server's message inline when confirming fails and keeps the buttons", async () => {
    const { api, typist } = await withProposal();
    api.schedules.generate.mockRejectedValue(
      new ApiError(
        409,
        'schedule_published',
        'This week is already published; it cannot be generated.',
      ),
    );

    await typist.click(screen.getByRole('button', { name: 'Confirm' }));

    const alert = await screen.findByRole('alert');
    expect(
      within(alert).getByText('This week is already published; it cannot be generated.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeEnabled();
  });

  it('cancelling writes nothing and says so', async () => {
    const { api, typist } = await withProposal();

    await typist.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(await screen.findByText('Proposal cancelled')).toBeInTheDocument();
    expect(api.schedules.generate).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Confirm' })).not.toBeInTheDocument(),
    );
  });
});
