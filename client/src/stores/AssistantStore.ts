import { makeAutoObservable, runInAction } from 'mobx';

import type { Api } from '../api';
import { ApiError, INTERNAL_ERROR_MESSAGE } from '../api/apiClient';
import type { ChatMessage, ScheduleProposal, ToolCall } from '../api/types/assistant';
import { failure, OK, type ActionResult } from './ScheduleStore';

/** The server accepts at most this many messages, each at most this long (schemas/assistant.py). */
const MAX_MESSAGES = 20;
const MAX_CHARACTERS = 2000;
const UNAVAILABLE_CODE = 'assistant_unavailable';

export type ProposalState = 'pending' | 'confirmed' | 'cancelled';

export interface ChatEntry {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  /** Handbook sections the answer names. */
  citations: string[];
  toolCalls: ToolCall[];
  proposal: ScheduleProposal | null;
  proposalState: ProposalState;
}

export interface AssistantStoreOptions {
  api: { assistant: Pick<Api['assistant'], 'chat'>; schedules: Pick<Api['schedules'], 'generate'> };
}

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : INTERNAL_ERROR_MESSAGE;
}

/**
 * The chat. The server keeps no conversation, so this store holds it and sends all of it (within
 * the server's limits) with each question. A proposal is only a proposal: confirming it calls the
 * normal generate endpoint, which is the one place a schedule is written.
 */
export class AssistantStore {
  messages: ChatEntry[] = [];
  isSending = false;
  error: string | null = null;
  /** True when the server says the assistant is off (no key, or the provider is down). */
  isUnavailable = false;
  isConfirming = false;

  private readonly api: AssistantStoreOptions['api'];
  private nextId = 1;

  constructor(options: AssistantStoreOptions) {
    this.api = options.api;
    makeAutoObservable<AssistantStore, 'api' | 'nextId'>(this, { api: false, nextId: false });
  }

  /** What the server gets: the last messages, each cut to the length it accepts. */
  get history(): ChatMessage[] {
    return this.messages.slice(-MAX_MESSAGES).map(({ role, content }) => ({
      role,
      content: content.slice(0, MAX_CHARACTERS),
    }));
  }

  get canRetry(): boolean {
    return this.error !== null && this.messages.at(-1)?.role === 'user';
  }

  async send(text: string): Promise<void> {
    const content = text.trim();
    if (!content || this.isSending) return;
    this.messages.push(this.entry('user', content));
    await this.ask();
  }

  /** Asks again after an error, without adding the question a second time. */
  async retry(): Promise<void> {
    if (!this.canRetry || this.isSending) return;
    await this.ask();
  }

  async confirmProposal(entryId: number): Promise<ActionResult> {
    const proposal = this.pendingProposal(entryId);
    if (!proposal || this.isConfirming) {
      return {
        ok: false,
        code: 'no_proposal',
        message: 'There is no proposal waiting to confirm.',
      };
    }
    this.isConfirming = true;
    try {
      await this.api.schedules.generate(proposal.week_start, {
        unavailable: proposal.unavailable.map(({ user_id, day }) => ({ user_id, day })),
      });
      runInAction(() => this.setProposalState(entryId, 'confirmed'));
      return OK;
    } catch (error) {
      return failure(error);
    } finally {
      runInAction(() => {
        this.isConfirming = false;
      });
    }
  }

  dismissProposal(entryId: number): void {
    if (this.pendingProposal(entryId)) this.setProposalState(entryId, 'cancelled');
  }

  reset(): void {
    this.messages = [];
    this.error = null;
    this.isUnavailable = false;
  }

  private async ask(): Promise<void> {
    this.isSending = true;
    this.error = null;
    this.isUnavailable = false;
    try {
      const reply = await this.api.assistant.chat(this.history);
      runInAction(() => {
        this.messages.push({
          ...this.entry('assistant', reply.message),
          citations: reply.citations,
          toolCalls: reply.tool_calls,
          proposal: reply.proposal,
        });
      });
    } catch (error) {
      runInAction(() => {
        this.error = messageOf(error);
        this.isUnavailable = error instanceof ApiError && error.code === UNAVAILABLE_CODE;
      });
    } finally {
      runInAction(() => {
        this.isSending = false;
      });
    }
  }

  private entry(role: ChatEntry['role'], content: string): ChatEntry {
    return {
      id: this.nextId++,
      role,
      content,
      citations: [],
      toolCalls: [],
      proposal: null,
      proposalState: 'pending',
    };
  }

  private pendingProposal(entryId: number): ScheduleProposal | null {
    const entry = this.messages.find((item) => item.id === entryId);
    return entry?.proposal && entry.proposalState === 'pending' ? entry.proposal : null;
  }

  private setProposalState(entryId: number, state: ProposalState): void {
    const entry = this.messages.find((item) => item.id === entryId);
    if (entry) entry.proposalState = state;
  }
}
