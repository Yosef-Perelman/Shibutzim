/** What the assistant looked at, in words a person recognizes; shown under an answer for trust. */
const TOOL_LABELS: Record<string, string> = {
  get_my_shifts: 'your shifts',
  get_my_hours: 'your hours',
  explain_pay: 'your pay',
  search_policy: 'the handbook',
  who_is_available: 'who is available',
  get_team_hours: "the team's hours",
  generate_schedule_draft: 'the scheduler',
};

/** The distinct labels of the tools used, in the order they were first called. */
export function lookedAt(toolNames: string[]): string[] {
  const labels = toolNames.map((name) => TOOL_LABELS[name] ?? name.replaceAll('_', ' '));
  return labels.filter((label, index) => labels.indexOf(label) === index);
}
