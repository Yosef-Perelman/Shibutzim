// Mirrors server/app/schemas/assistant.py; snake_case fields as the server sends them.

export type ChatRole = 'user' | 'assistant';

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

/** What the assistant looked up: the tool and its arguments, not the result. */
export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
}

export interface DayOff {
  user_id: number;
  name: string;
  /** Local calendar date, `YYYY-MM-DD`. */
  day: string;
}

export interface ProposedShift {
  shift_id: number;
  date: string;
  weekday: string;
  name: string;
  start: string;
  end: string;
  people: string[];
}

/** A schedule the manager may confirm; nothing is saved until then. */
export interface ScheduleProposal {
  type: 'schedule_draft';
  week_start: string;
  unavailable: DayOff[];
  summary: string;
  filled: number;
  required: number;
  replaces_draft: boolean;
  assignments: ProposedShift[];
  unfilled: string[];
}

export interface ChatOut {
  message: string;
  /** Handbook section titles the answer names. */
  citations: string[];
  tool_calls: ToolCall[];
  proposal: ScheduleProposal | null;
}
