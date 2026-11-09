# Shibutzim – Glossary

> Domain terms and their **exact names** in code, database and API. When a term here and a name in the code
> disagree, one of them is a bug. Update this file in the same change that introduces or renames a concept.

## 1. Naming conventions

| Where | Convention | Example |
|---|---|---|
| Python modules, functions, variables | `snake_case` | `calculate_pay`, `week_start` |
| Python classes, Pydantic schemas | `PascalCase` | `TimeEntry`, `PayBreakdown` |
| Database tables | plural `snake_case` | `time_entries`, `shift_templates` |
| Database columns | `snake_case`, same word as the Python attribute | `required_staff`, `clock_in` |
| API paths | plural, kebab-case resources | `/api/time-entries`, `/api/shift-templates` |
| API JSON fields | `snake_case`, identical to the Python schema | `"week_start"`, `"hourly_rate"` |
| TypeScript types | `PascalCase`, mirroring the Pydantic schema | `TimeEntry`, `PayBreakdown` |
| TypeScript fields | `snake_case`, identical to the JSON | `week_start` |
| Enum values | lowercase strings | `"manager"`, `"preferred"`, `"draft"` |
| Error codes | lowercase `snake_case` strings | `"forbidden"`, `"shift_overlap"` |

One name travels unchanged from the database to the TypeScript type. The small cost in JavaScript style buys zero
mapping code and one vocabulary for people and agents.

## 2. Terms

### People and access

| Term | Meaning | Code · DB · API |
|---|---|---|
| **User** | a person who can log in | `User` · `users` · `/api/users` |
| **Role** | what a user may do: `manager` or `employee` | `Role` enum · `users.role` · `"role"` |
| **Manager** | user with role `manager`; runs the team | `Role.manager` |
| **Employee** | user with role `employee`; works shifts | `Role.employee` |
| **Current user** | the authenticated user a request or tool call runs as | `current_user` dependency / parameter |
| **Hourly rate** | an employee's base pay per hour | `hourly_rate` · `users.hourly_rate` (numeric) · `"hourly_rate"` (string) |

### Scheduling

| Term | Meaning | Code · DB · API |
|---|---|---|
| **Shift template** | recurring slot: weekday, start, end, required staff | `ShiftTemplate` · `shift_templates` · `/api/shift-templates` |
| **Required staff** | how many employees a shift needs | `required_staff` |
| **Week** | scheduling week, Sunday to Saturday, identified by its Sunday | `week_start` (date) |
| **Shift** | concrete slot in a specific week, generated from a template | `Shift` · `shifts` · `/api/shifts` |
| **Availability** | an employee's answer for one shift | `Availability` · `availabilities` · `/api/availabilities` |
| **Availability status** | `available` \| `preferred` \| `unavailable`; a missing answer counts as `unavailable` | `AvailabilityStatus` enum · `availabilities.status` |
| **Schedule** | all assignments of one week, with a status | `Schedule` · `schedules` · `/api/schedules/{week_start}` |
| **Schedule status** | `draft` (manager only) \| `published` (visible to employees) | `ScheduleStatus` enum · `schedules.status` |
| **Assignment** | employee X is planned for shift Y | `Assignment` · `assignments` |
| **Generate** | run the solver for a week and store the result as the draft | `POST /api/schedules/{week_start}/generate` |
| **Publish** | mark a schedule `published` | `POST /api/schedules/{week_start}/publish` |
| **Solver** | the pure scheduling algorithm | `scheduler.solve(shifts, employees, availabilities, rules)` |
| **Hard constraint** | a rule the solver never violates (availability, required staff, no overlap, minimum rest, max shifts per week) | `scheduler/constraints.py` |
| **Soft constraint** | a preference the solver scores (fair hours, preferred shifts) | `scheduler/scoring.py` |
| **Minimum rest** | required gap between two shifts of one employee; default 8 hours | `SchedulingRules.min_rest_hours` |
| **Max shifts per week** | per-employee cap; default 5 | `SchedulingRules.max_shifts_per_week` |
| **Schedule result** | solver output: assignments, score, unfilled slots with reasons | `ScheduleResult` |
| **Unfilled slot** | a required position on a shift the solver could not staff, with the reason | `UnfilledSlot` |
| **Trace (explain) mode** | solver option that records which constraint eliminated which candidate for which slot | `solve(..., trace=True)` → `ScheduleResult.trace` |

### Time and pay

| Term | Meaning | Code · DB · API |
|---|---|---|
| **Time entry** | actual clock-in and clock-out of one employee | `TimeEntry` · `time_entries` · `/api/time-entries` |
| **Clock in / clock out** | opening / closing a time entry | `clock_in`, `clock_out` (timestamptz; `clock_out` is null while open) |
| **Open entry** | a time entry without clock-out; at most one per employee | `clock_out IS NULL` |
| **Time entry source** | how the entry was created: `clock` (employee) or `manual` (manager) | `TimeEntrySource` enum · `time_entries.source` |
| **Split shift** | two or more time entries on the same work day | no entity; a pattern of entries |
| **Work day** | the calendar day (in `Asia/Jerusalem`) on which a time entry **started**; the unit for overtime tiers | `work_day` (date) in pay code |
| **Pay period** | calendar month; the default reporting range | `from`, `to` query parameters |
| **Pay rules** | all configuration the pay calculation needs: tiers (and later premiums) | `PayRules` |
| **Overtime tier** | a band of daily hours with a rate multiplier (1–8 h → 1.00, 9–10 h → 1.25, 11+ h → 1.50) | `OvertimeTier(from_hour, to_hour, multiplier)` |
| **Pay calculation** | pure function from entries, rate and rules to a breakdown | `pay.calculate(entries, hourly_rate, rules)` |
| **Pay breakdown** | the result: per work day the hours and amount per tier, plus totals | `PayBreakdown`, `DayBreakdown`, `TierLine` · `GET /api/pay` |

### Assistant

| Term | Meaning | Code · DB · API |
|---|---|---|
| **Assistant** | the AI agent users chat with | `assistant/` · `POST /api/assistant/chat` |
| **Agent loop** | the cycle: model → tool call → tool result → model, until a text answer | `assistant/agent.py` |
| **Tool** | a function the model may call; runs services as the current user | `assistant/tools/` |
| **Read tool** | a tool that only reads | e.g. `get_my_hours` |
| **Write tool** | a tool that would change data; returns a proposal instead | e.g. `generate_schedule_draft` |
| **Proposal** | a write tool's output: the intended change plus a summary; applied only after the user confirms through the REST endpoint | `Proposal` schema · `"proposal"` field in the chat response |
| **Tool call log** | audit record of one tool call: tool, args, user, duration, result size, status | `ToolCallLog` · `tool_call_logs` |
| **LLM adapter** | the single interface to a model provider: chat with tool calling, embeddings | `assistant/llm/` (`LLM` protocol, `GeminiLLM`) |
| **Prompt** | system prompt or tool description, kept in a file | `assistant/prompts/*.md` |
| **Handbook** | the invented company policy document (markdown, ~10 sections) | `server/handbook/` |
| **Chunk** | one handbook section with its embedding | `HandbookChunk` · `handbook_chunks` |
| **Ingestion** | splitting, embedding and storing the handbook | `scripts/ingest_handbook.py` |
| **Citation** | the section title the assistant names when answering from the handbook | `section_title` in `search_policy` results |
| **Eval** | a fixed question with expected tool calls, expected facts and required citation | `server/evals/` |

## 3. Time vocabulary

| Term | Definition |
|---|---|
| **Week** | Sunday 00:00 to Saturday 23:59:59 in `Asia/Jerusalem`; identified by `week_start`, the Sunday's date |
| **Weekday** | integer 0–6 where 0 = Sunday |
| **Work day** | the `Asia/Jerusalem` date of a time entry's `clock_in`; an entry crossing midnight stays on that day |
| **Pay period** | a calendar month |
| **Storage** | every timestamp is stored in UTC as `timestamptz`; conversion to `Asia/Jerusalem` happens only for day and week boundaries and for display |

## 4. Planned vs. actual

**Assignment** is what was planned. **Time entry** is what happened. They are different tables, different
endpoints and different concepts. **Pay is computed from time entries only**; the schedule never produces pay,
and clocking in never changes the schedule.
