import type { ApiClient } from './apiClient';
import type { ChatMessage, ChatOut } from './types/assistant';

export function createAssistantApi(client: ApiClient) {
  return {
    /** The server keeps no conversation: every call carries the whole history. */
    chat: (messages: ChatMessage[]) => client.post<ChatOut>('/api/assistant/chat', { messages }),
  };
}
