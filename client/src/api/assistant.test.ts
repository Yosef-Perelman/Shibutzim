import { describe, expect, it, vi } from 'vitest';

import type { ApiClient } from './apiClient';
import { createAssistantApi } from './assistant';
import { createSchedulesApi } from './schedules';

function fakeClient() {
  return { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() };
}

describe('createAssistantApi', () => {
  it('posts the whole history to the chat endpoint', async () => {
    const client = fakeClient();
    client.post.mockResolvedValue({ message: 'Hi', citations: [], tool_calls: [], proposal: null });
    const api = createAssistantApi(client as unknown as ApiClient);

    const reply = await api.chat([{ role: 'user', content: 'hello' }]);

    expect(client.post).toHaveBeenCalledWith('/api/assistant/chat', {
      messages: [{ role: 'user', content: 'hello' }],
    });
    expect(reply.message).toBe('Hi');
  });
});

describe('createSchedulesApi.generate', () => {
  it('sends no body when there are no days off, as before', async () => {
    const client = fakeClient();
    const api = createSchedulesApi(client as unknown as ApiClient);

    await api.generate('2026-11-15');

    expect(client.post).toHaveBeenCalledWith('/api/schedules/2026-11-15/generate', undefined);
  });

  it('sends the days off the manager confirmed', async () => {
    const client = fakeClient();
    const api = createSchedulesApi(client as unknown as ApiClient);

    await api.generate('2026-11-15', { unavailable: [{ user_id: 3, day: '2026-11-17' }] });

    expect(client.post).toHaveBeenCalledWith('/api/schedules/2026-11-15/generate', {
      unavailable: [{ user_id: 3, day: '2026-11-17' }],
    });
  });
});
