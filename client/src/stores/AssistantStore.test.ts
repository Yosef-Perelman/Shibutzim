import { describe, expect, it, vi } from 'vitest';

import { ApiError } from '../api/apiClient';
import type { ChatOut, ScheduleProposal } from '../api/types/assistant';
import { AssistantStore } from './AssistantStore';

function reply(overrides: Partial<ChatOut> = {}): ChatOut {
  return {
    message: 'You worked 8 hours.',
    citations: [],
    tool_calls: [],
    proposal: null,
    ...overrides,
  };
}

function makeProposal(overrides: Partial<ScheduleProposal> = {}): ScheduleProposal {
  return {
    type: 'schedule_draft',
    week_start: '2026-11-15',
    unavailable: [{ user_id: 3, name: 'Noa Katz', day: '2026-11-17' }],
    summary: '20 of 21 positions filled. 1 shift is short of staff.',
    filled: 20,
    required: 21,
    replaces_draft: false,
    assignments: [],
    unfilled: ['Tuesday 07:00 needs 2, only 1 available'],
    ...overrides,
  };
}

function setup() {
  const api = { assistant: { chat: vi.fn() }, schedules: { generate: vi.fn() } };
  const store = new AssistantStore({ api });
  return { api, store };
}

describe('AssistantStore.send', () => {
  it('shows the question at once and the answer when it arrives', async () => {
    const { api, store } = setup();
    api.assistant.chat.mockResolvedValue(
      reply({ citations: ['Breaks'], tool_calls: [{ name: 'get_my_hours', args: { from: 'a' } }] }),
    );

    const pending = store.send('How many hours?');
    expect(store.isSending).toBe(true);
    expect(store.messages.map((m) => m.content)).toEqual(['How many hours?']);
    await pending;

    expect(store.isSending).toBe(false);
    expect(store.messages.map((m) => [m.role, m.content])).toEqual([
      ['user', 'How many hours?'],
      ['assistant', 'You worked 8 hours.'],
    ]);
    expect(store.messages[1]).toMatchObject({
      citations: ['Breaks'],
      toolCalls: [{ name: 'get_my_hours', args: { from: 'a' } }],
      proposal: null,
    });
  });

  it('sends the whole conversation each time', async () => {
    const { api, store } = setup();
    api.assistant.chat.mockResolvedValue(reply({ message: 'Which month?' }));
    await store.send('How many hours?');
    api.assistant.chat.mockResolvedValue(reply());

    await store.send('March');

    expect(api.assistant.chat).toHaveBeenLastCalledWith([
      { role: 'user', content: 'How many hours?' },
      { role: 'assistant', content: 'Which month?' },
      { role: 'user', content: 'March' },
    ]);
  });

  it('sends at most the last twenty messages, each at most 2000 characters', async () => {
    const { api, store } = setup();
    api.assistant.chat.mockResolvedValue(reply({ message: 'x'.repeat(2500) }));
    for (let index = 0; index < 11; index += 1) await store.send(`question ${index}`);

    const history = api.assistant.chat.mock.calls.at(-1)?.[0] as {
      role: string;
      content: string;
    }[];

    expect(history).toHaveLength(20);
    expect(history.at(-1)).toEqual({ role: 'user', content: 'question 10' });
    expect(history.every((message) => message.content.length <= 2000)).toBe(true);
  });

  it('ignores a blank question and a question while one is running', async () => {
    const { api, store } = setup();
    let finish: (value: ChatOut) => void = () => undefined;
    api.assistant.chat.mockReturnValue(new Promise((resolve) => (finish = resolve)));

    await store.send('   ');
    const first = store.send('one');
    await store.send('two');
    finish(reply());
    await first;

    expect(api.assistant.chat).toHaveBeenCalledTimes(1);
    expect(store.messages.filter((m) => m.role === 'user')).toHaveLength(1);
  });

  it('trims the question', async () => {
    const { api, store } = setup();
    api.assistant.chat.mockResolvedValue(reply());

    await store.send('  hello  ');

    expect(store.messages[0]?.content).toBe('hello');
  });
});

describe('AssistantStore errors', () => {
  it('keeps the question and shows the server message when the answer fails', async () => {
    const { api, store } = setup();
    api.assistant.chat.mockRejectedValue(
      new ApiError(500, 'internal_error', 'Something went wrong.'),
    );

    await store.send('hi');

    expect(store.error).toBe('Something went wrong.');
    expect(store.isUnavailable).toBe(false);
    expect(store.messages.map((m) => m.role)).toEqual(['user']);
  });

  it('knows when the assistant is not available at all', async () => {
    const { api, store } = setup();
    api.assistant.chat.mockRejectedValue(
      new ApiError(503, 'assistant_unavailable', 'The assistant is not available right now.'),
    );

    await store.send('hi');

    expect(store.isUnavailable).toBe(true);
    expect(store.error).toBe('The assistant is not available right now.');
  });

  it('retries the last question without adding it twice', async () => {
    const { api, store } = setup();
    api.assistant.chat.mockRejectedValueOnce(new ApiError(500, 'internal_error', 'Oops.'));
    await store.send('hi');
    api.assistant.chat.mockResolvedValue(reply());

    await store.retry();

    expect(store.error).toBeNull();
    expect(store.messages.map((m) => m.role)).toEqual(['user', 'assistant']);
    expect(api.assistant.chat).toHaveBeenLastCalledWith([{ role: 'user', content: 'hi' }]);
  });

  it('clears the error when the next question succeeds', async () => {
    const { api, store } = setup();
    api.assistant.chat.mockRejectedValueOnce(new ApiError(500, 'internal_error', 'Oops.'));
    await store.send('hi');
    api.assistant.chat.mockResolvedValue(reply());

    await store.send('again');

    expect(store.error).toBeNull();
  });

  it('does not retry when the last message is already answered', async () => {
    const { api, store } = setup();
    api.assistant.chat.mockResolvedValue(reply());
    await store.send('hi');

    await store.retry();

    expect(api.assistant.chat).toHaveBeenCalledTimes(1);
  });
});

describe('AssistantStore proposals', () => {
  async function withProposal() {
    const ctx = setup();
    ctx.api.assistant.chat.mockResolvedValue(reply({ proposal: makeProposal() }));
    await ctx.store.send("Build next week's schedule");
    const entry = ctx.store.messages[1];
    if (!entry) throw new Error('no answer');
    return { ...ctx, entry };
  }

  it('shows a proposal as waiting for the manager', async () => {
    const { entry } = await withProposal();

    expect(entry.proposal?.summary).toContain('20 of 21');
    expect(entry.proposalState).toBe('pending');
  });

  it('confirming calls the normal generate endpoint with the days off', async () => {
    const { api, store, entry } = await withProposal();
    api.schedules.generate.mockResolvedValue({});

    const result = await store.confirmProposal(entry.id);

    expect(api.schedules.generate).toHaveBeenCalledWith('2026-11-15', {
      unavailable: [{ user_id: 3, day: '2026-11-17' }],
    });
    expect(result).toEqual({ ok: true, warnings: [] });
    expect(store.messages[1]?.proposalState).toBe('confirmed');
  });

  it('keeps the proposal waiting and returns the server message when confirming fails', async () => {
    const { api, store, entry } = await withProposal();
    api.schedules.generate.mockRejectedValue(
      new ApiError(
        409,
        'schedule_published',
        'This week is already published; it cannot be generated.',
      ),
    );

    const result = await store.confirmProposal(entry.id);

    expect(result).toEqual({
      ok: false,
      code: 'schedule_published',
      message: 'This week is already published; it cannot be generated.',
    });
    expect(store.messages[1]?.proposalState).toBe('pending');
  });

  it('is working while the generate request runs and cannot be confirmed twice', async () => {
    const { api, store, entry } = await withProposal();
    let finish: (value: unknown) => void = () => undefined;
    api.schedules.generate.mockReturnValue(new Promise((resolve) => (finish = resolve)));

    const first = store.confirmProposal(entry.id);
    expect(store.isConfirming).toBe(true);
    await store.confirmProposal(entry.id);
    finish({});
    await first;

    expect(api.schedules.generate).toHaveBeenCalledTimes(1);
    expect(store.isConfirming).toBe(false);
  });

  it('cancelling writes nothing', async () => {
    const { api, store, entry } = await withProposal();

    store.dismissProposal(entry.id);

    expect(store.messages[1]?.proposalState).toBe('cancelled');
    expect(api.schedules.generate).not.toHaveBeenCalled();
  });

  it('cannot confirm a cancelled or unknown proposal', async () => {
    const { api, store, entry } = await withProposal();
    store.dismissProposal(entry.id);

    const cancelled = await store.confirmProposal(entry.id);
    const unknown = await store.confirmProposal(9999);

    expect(cancelled.ok).toBe(false);
    expect(unknown.ok).toBe(false);
    expect(api.schedules.generate).not.toHaveBeenCalled();
  });
});

describe('AssistantStore.reset', () => {
  it('forgets the conversation', async () => {
    const { api, store } = setup();
    api.assistant.chat.mockResolvedValue(reply());
    await store.send('hi');

    store.reset();

    expect(store.messages).toEqual([]);
    expect(store.error).toBeNull();
  });
});
