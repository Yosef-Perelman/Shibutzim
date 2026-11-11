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
| **Login** | exchange email and password for an access token; every failure looks the same | `POST /api/auth/login` · `LoginRequest`, `TokenOut` |
| **Access token** | JWT (HS256) with `sub` (user id) and `role`; valid 8 hours; sent as `Authorization: Bearer` | `create_access_token`, `TokenClaims` |
| **Current user endpoint** | the authenticated user's own profile | `GET /api/auth/me` · `UserOut` |
| **User list** | managers only: every user, filtered by `role` and `is_active`, ordered by name; feeds the employee picker of the schedule board | `GET /api/users` · `user_service.list_users` · `UserOut` |
| **Demo user** | a user created by the seed; all share the password in `SEED_PASSWORD` | `scripts/seed.py` |
| **Hourly rate** | an employee's base pay per hour | `hourly_rate` · `users.hourly_rate` (numeric) · `"hourly_rate"` (string) |

### Scheduling

| Term | Meaning | Code · DB · API |
|---|---|---|
| **Shift template** | recurring slot: weekday, start, end, required staff; an end at or before the start ends the next day; deactivated (`is_active = false`), never deleted; editing it never changes shifts already generated | `ShiftTemplate` · `shift_templates` · `GET`, `POST`, `PATCH /api/shift-templates` (managers) |
| **Required staff** | how many employees a shift needs | `required_staff` |
| **Week** | scheduling week, Sunday to Saturday, identified by its Sunday | `week_start` (date) |
| **Shift** | concrete slot in a specific week, generated from a template; snapshots the template's times and `required_staff` | `Shift` · `shifts` · `GET /api/shifts?week_start=` |
| **Shift generation** | create the week's missing shifts from the active templates; running it again adds only what is missing | `POST /api/shifts/generate` (managers) · `shift_service.generate_shifts` |
| **Availability** | an employee's answer for one shift | `Availability` · `availabilities` · `GET`, `PUT /api/availabilities` |
| **Availability lock** | employees can no longer answer for a week once a schedule exists for it or the week is over; managers never are locked | `availability_locked` |
| **Availability status** | `available` \| `preferred` \| `unavailable`; a missing answer counts as `unavailable` | `AvailabilityStatus` enum · `availabilities.status` |
| **Schedule** | all assignments of one week, with a status | `Schedule` · `schedules` · `/api/schedules/{week_start}` |
| **Schedule status** | `draft` (manager only) \| `published` (visible to employees) | `ScheduleStatus` enum · `schedules.status` |
| **Assignment** | employee X is planned for shift Y | `Assignment` · `assignments` |
| **Generate** | run the solver for a week and store the result as the draft, replacing the current draft; never replaces a published schedule | `POST /api/schedules/{week_start}/generate` · `schedule_service.generate_schedule` |
| **Dry run (proposal)** | run the solver for a week without saving anything; used by the assistant's write tool and by `debug-schedule`, with optional rules and trace | `schedule_service.propose_schedule` · `Proposal` |
| **Assignment edit** | a manager adds, replaces (the "swap") or removes one assignment of a draft or published schedule; overlap and minimum rest are rejected, the rest warns | `POST .../assignments`, `PATCH`, `DELETE .../assignments/{id}` · `assignment_service` |
| **Edit warning** | a rule an assignment edit bent but did not block: `availability_ignored`, `max_shifts_exceeded`, `shift_overstaffed` | `EditWarning` · `warnings` in the response |
| **Publish** | mark a schedule `published` | `POST /api/schedules/{week_start}/publish` |
| **Solver** | the pure scheduling algorithm: backtracking search with forward checking for coverage, then a hill-climbing polish for the soft constraints | `scheduler.solve(shifts, employees, availabilities, rules, trace=False)` |
| **Search budget** | the number of search nodes the solver may use (`max_steps`), not a time, so a solve is reproducible; the best result found is returned and `complete` says whether the search finished | `SchedulingRules.max_steps` · `ScheduleResult.complete` |
| **Hard constraint** | a rule the solver never violates (availability, required staff, no overlap, minimum rest, max shifts per week) | `scheduler/constraints.py` |
| **Soft constraint** | a preference the solver scores (fair hours, preferred shifts) | `scheduler/scoring.py` |
| **Minimum rest** | required gap between the end of one shift and the start of the next of one employee, measured in real elapsed time; default 8 hours. v1 checks one week at a time, so rest across the Saturday-Sunday boundary is not checked | `SchedulingRules.min_rest_hours` · `min_rest`, `min_rest_violation` |
| **Max shifts per week** | per-employee cap; default 5 | `SchedulingRules.max_shifts_per_week` |
| **Scheduling rules** | all configuration the solver needs: minimum rest, max shifts per week, search budget; from `SCHEDULER_*` environment variables | `SchedulingRules` · `Settings.scheduling_rules` |
| **Schedule result** | solver output: assignments, score, unfilled slots with reasons, steps used | `ScheduleResult` |
| **Score** | the solver's objective: positions filled first, then `preferred_count × 120 − hours spread` (spread in minutes between the most and least hours among employees who answered) | `Score` · `scoring.PREFERRED_WEIGHT` |
| **Unfilled slot** | the missing positions of one shift (`required` minus `assigned`), with why each other employee could not take it | `UnfilledSlot` · `unfilled` in the generate response |
| **Exclusion** | one employee excluded from one shift by one hard constraint (`availability`, `overlap`, `min_rest`, `max_shifts`), naming the conflicting shift when there is one | `Exclusion` · `Constraint` |
| **Explanation** | the sentence for an unfilled slot, e.g. "Tuesday 07:00 needs 3, only 2 available; Dana excluded by minimum rest" | `scheduler.explain.explain` · `sentence` |
| **Trace (explain) mode** | solver option that records every placement, backtrack and candidate eliminated by forward checking (capped at 20 000 events) | `solve(..., trace=True)` → `ScheduleResult.trace` of `TraceEvent` |

### Time and pay

| Term | Meaning | Code · DB · API |
|---|---|---|
| **Time entry** | actual clock-in and clock-out of one employee | `TimeEntry` · `time_entries` · `/api/time-entries` |
| **Clock in / clock out** | opening / closing a time entry | `clock_in`, `clock_out` (timestamptz; `clock_out` is null while open) |
| **Open entry** | a time entry without clock-out; at most one per employee | `clock_out IS NULL` |
| **Manual entry** | a closed time entry a manager records for an employee (`source = manual`, `created_by` = the manager) | `POST /api/time-entries` · `TimeEntryCreate` |
| **Correction** | a manager's partial change to an entry's times or note; the merged interval is re-validated | `PATCH /api/time-entries/{id}` · `TimeEntryUpdate` |
| **Maximum entry length** | an entry may not exceed 24 hours; a forgotten clock-out must be corrected by a manager | `MAX_ENTRY_DURATION` · `entry_too_long` |
| **Time entry overlap** | two entries of one employee that intersect (half-open intervals; an open entry extends forever); rejected because it would double-count pay | `time_entry_overlap` |
| **Time entry source** | how the entry was created: `clock` (employee) or `manual` (manager) | `TimeEntrySource` enum · `time_entries.source` |
| **Split shift** | two or more time entries on the same work day | no entity; a pattern of entries |
| **Work day** | the calendar day (in `Asia/Jerusalem`) on which a time entry **started**; the unit for overtime tiers | `work_day` (date) in pay code |
| **Pay period** | calendar month; the default reporting range | `from`, `to` query parameters |
| **Pay rules** | all configuration the pay calculation needs: tiers (and later premiums) | `PayRules` |
| **Overtime tier** | a band of daily hours with a rate multiplier (1–8 h → 1.00, 9–10 h → 1.25, 11+ h → 1.50) | `OvertimeTier(from_hour, to_hour, multiplier)` |
| **Pay calculation** | pure function from closed entries, rate, rules and zone to a breakdown | `pay.calculate(entries, hourly_rate, rules, tz)` |
| **Pay breakdown** | the result: per work day the hours and amount per tier, plus totals | `PayBreakdown`, `DayBreakdown`, `TierLine` · `GET /api/pay` |
| **Pay entry** | a closed time entry reduced to `clock_in` and `clock_out`; the input of the pay calculation | `pay.Entry` |
| **Team pay** | every active user's pay for a range (plus deactivated users who worked in it); managers only | `GET /api/pay/team` · `TeamPayOut`, `TeamPayRow` |
| **Open entries (in pay)** | entries without a clock-out in the range; excluded from pay and reported as a count | `open_entries` |
| **Display hours** | hours in pay responses, rounded to two decimals for display only; `seconds` is the exact duration | `hours` next to `seconds` |
| **Work-day range** | `from` and `to` query parameters: first and last work day, both inclusive; an entry belongs to the range if its work day does | `from`, `to` |

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
