# Shibutzim – Product Definition

> **Shibutzim** (שיבוצים) is Hebrew for "assignments": assigning employees to shifts.
> This document is the single source of truth for *what* the product does and *why*.
> For *how* it is built see [architecture.md](architecture.md); for vocabulary see [glossary.md](glossary.md).

## 1. Purpose

**One-liner:** shift scheduling and pay for small teams of hourly workers, with an AI assistant that answers
questions about shifts, pay and company policy **from real app data**.

Shibutzim is a portfolio project in the hourly-workforce domain. It is built to be small enough to understand
end to end, while exercising real production concerns: server-side authorization, deterministic money
calculations, constraint-based scheduling, and an LLM agent that is bounded by code rather than by prompts.

Scope anchors for v1:

- **One organization.** No multi-tenancy. One team, one manager role, several employees.
- **Seeded demo data.** Demo users are created by a seed script, and the client offers a quick way to switch
  between a manager and an employee account.
- **Web only.** The employee experience is a mobile-friendly web app, not a native app.

## 2. Problem

Small teams of hourly workers (a café, a small clinic, a shop) usually schedule by hand:

- The manager collects availability over chat messages, builds the week in a spreadsheet, and reposts it after
  every change. Nobody is sure which version is current.
- Hours are reconstructed at month end from memory or paper. Overtime rules (daily tiers, split shifts, shifts that
  cross midnight) are applied inconsistently, so pay disputes are common.
- Employees cannot check their own hours or pay during the month, and every policy question ("can I swap a shift?",
  "how is overtime paid?") lands on the manager.

Shibutzim replaces this with one place to collect availability, generate and publish a schedule, record actual
work, compute pay deterministically, and let people ask questions in natural language and get answers that are
grounded in the data and the policy document.

## 3. Users and roles

| Role | Where | Can do |
|---|---|---|
| **Manager** | web (desktop) | define shift templates and required staff; generate the weekly schedule; edit and publish it; see everyone's hours and pay; add or correct time entries; ask the assistant team-level questions |
| **Employee** | web (mobile-friendly) | submit weekly availability; see everyone's published schedule; clock in and out; see own hours and pay; ask the assistant about own data and policies |

**Roles are enforced on the server, in the service layer.** The client only hides what a role may not use; it is
never the line of defense. The same rule applies to the AI assistant: its tools run as the current user through the
same services, so the assistant can never see or change more than the user could through the UI.

## 4. Planned vs. actual

The most important distinction in the domain:

| | What it is | Where it lives | Used for |
|---|---|---|---|
| **Assignment** | employee X is *planned* to work shift Y | the published schedule | the schedule board, "my shifts" |
| **Time entry** | employee X *actually* clocked in and out | time tracking | hours and pay |

**Pay is computed from time entries only.** An assignment never creates pay; a time entry never changes the
schedule. Comparing the two ("planned 40h, worked 43h") is a natural later feature.

## 5. MVP features

### 5.1 Availability

An employee marks, for each shift of **next week**, one of three statuses: `available`, `preferred`, `unavailable`.

Acceptance criteria:

- The employee sees next week's shifts (generated from the shift templates) and can set or change a status per
  shift until the manager generates the schedule.
- A shift with **no answer counts as `unavailable`** for the solver. Opting in is explicit.
- Availability for past weeks is read-only.

### 5.2 Auto-scheduling

The manager clicks **Generate** for a week. The solver (a constraint-satisfaction search, see
[architecture.md](architecture.md)) produces a **draft** schedule that the manager edits and then **publishes**.

Acceptance criteria:

- Generate creates a draft; generating again replaces the current draft. A published schedule is never replaced by
  Generate.
- The draft respects every **hard constraint**: an employee is only placed on a shift they marked `available` or
  `preferred`; each shift gets its `required_staff`; no employee works two overlapping shifts; a minimum rest
  (default 8 hours, configurable) separates an employee's consecutive shifts; no employee has more than 5 shifts
  per week.
- The solver optimizes **soft constraints**: fair distribution of hours across employees and honoring `preferred`
  shifts.
- If a shift cannot be fully staffed, the draft is still returned and the response lists each unfilled slot with the
  reason (for example "Tuesday 07:00 needs 3, only 2 available; Dana excluded by minimum rest").
- The manager can add, remove or swap assignments in the draft. Edits that break **overlap** or **minimum rest**
  are rejected. Edits that ignore **availability** are allowed with a warning, because the manager may know
  something the system does not.
- **Publish** marks the schedule `published`; from that moment employees see it. Changes after publishing are
  allowed and are visible immediately (no re-publish step in v1).

### 5.3 Time tracking

Employees record actual work; managers correct it.

Acceptance criteria:

- **Clock in** opens a time entry; **clock out** closes it. An employee cannot have two open entries.
- Several entries per day are allowed (a **split shift**, e.g. 07:00–11:00 and 16:00–22:00).
- An entry may **cross midnight** (22:00–06:00). It belongs to the **work day on which it started**.
- Work-day boundaries are computed in `Asia/Jerusalem`; all timestamps are stored in UTC.
- A manager can add a manual entry or correct any entry for any employee. Each entry records its `source`
  (`clock` or `manual`) and who created it.
- Validation: clock-out must be after clock-in; an entry longer than 24 hours is rejected.

### 5.4 Pay calculation

Pay is a **deterministic, pure, fully unit-tested** function of time entries and pay rules.

Acceptance criteria:

- `GET /api/pay` returns, for a date range, a **breakdown**: per work day the hours in each tier and the amount,
  plus totals. An employee gets their own; a manager may request anyone's or the whole team's.
- Rules v1 (see §6.1) are applied **per work day**, after summing all of that day's entries.
- Money is `Decimal`, rounded to the cent only in the final amounts, never in intermediate hours.
- The required unit-test matrix is part of the definition: exactly 8h; 9h; 12h; split shift (07–11 + 16–22 = 10h);
  22:00–06:00 crossing midnight; two work days in one period; no entries; rounding to the cent.

### 5.5 AI assistant

A chat where a user asks questions about shifts, pay and policy, and the assistant answers by calling tools that
run the same services as the UI.

Acceptance criteria:

- Answers about numbers (hours, pay) come from tool results; the model explains them and never computes them.
- Policy answers come from the **employee handbook** via retrieval, and the answer **cites the section title**.
- A **write** request ("build next week's schedule, Dana can't work Tuesday") produces a **proposal** shown with
  **Confirm / Cancel**. Confirming calls the normal REST endpoint; nothing is written until then.
- The assistant refuses, with a clear message, anything outside its tools or outside the user's role.
- Every tool call is logged with tool name, arguments, user, duration and result size.
- Conversation state is held by the client in v1 (the client sends the history with each message).

## 6. Business rules

### 6.1 Pay rules (v1)

- Each employee has a **base hourly rate**.
- Per **work day**, after summing all entries that started on that day:

  | Hours of the day | Rate |
  |---|---|
  | 1–8 | 100 % |
  | 9–10 | 125 % |
  | 11 and above | 150 % |

- Tiers are **configurable** and the pay module is designed so that new rules (night premium, weekend premium) can
  be added without rewriting the tier logic.
- An entry that crosses midnight belongs to the day it **started**; it is not split at midnight.
- **Split shifts** on one work day are summed **before** tiers apply (4h + 6h = 10h → 8h at 100 %, 2h at 125 %).
- The pay period is the **calendar month**. Reports may use any date range.
- Unpaid breaks are not modeled in v1.
- Overtime is **daily only** in v1; weekly overtime is a planned extension.

### 6.2 Scheduling rules (v1)

- A **week starts on Sunday** and is identified by that Sunday's date (`week_start`).
- Shifts for a week are generated from the active **shift templates** (weekday, start, end, `required_staff`).
- **Hard constraints** (never violated by the solver): availability, `required_staff`, no overlap, minimum rest
  (default 8h), max 5 shifts per employee per week.
- **Soft constraints** (optimized): fair distribution of hours, `preferred` shifts honored.
- The solver has a search budget (a count of search steps, so results are reproducible) and returns the best schedule
  found, with an explanation of what could not be filled.

### 6.3 Time conventions

- Work-day and week boundaries are computed in **`Asia/Jerusalem`**.
- Every timestamp is timezone-aware; the database stores **UTC**.

## 7. AI assistant principles

These principles are the product's stance on AI and are enforced in code, not only described in prompts:

1. **The LLM never does arithmetic or scheduling.** It calls deterministic code (`pay`, `scheduler`) and explains
   the result.
2. **Permissions are enforced in the tool layer, not in the prompt.** Tools call services as the current user, so
   the assistant inherits exactly the UI's authorization.
3. **Write tools return a proposal.** A human confirms in the UI; confirming calls the normal REST endpoint.
4. **Every tool call is logged** (tool, arguments, user, duration, result size).
5. **Evals guard behavior.** A fixed set of about 15 questions with expected tool calls, expected facts and
   required citations runs after every change to prompts or tools.
6. **Prompts live in files**, never in inline strings, so they are reviewed like code.

### Tools (initial)

| Tool | Who | Type |
|---|---|---|
| `get_my_shifts(from, to)` | employee | read |
| `get_my_hours(from, to)` | employee | read |
| `explain_pay(from, to)` – runs the pay calculation and explains each tier | employee | read |
| `search_policy(query)` – retrieval over the handbook, returns chunks with section titles | both | read |
| `who_is_available(day, shift?)` or `(shift_id)` – who answered what for one shift | manager | read |
| `get_team_hours(from, to)` | manager | read |
| `generate_schedule_draft(week_start, unavailable)` – e.g. "Noa is off Tuesday" | manager | write → proposal |

### Example questions

- "Why is my pay lower than last week?"
- "How much overtime did I do this month?"
- "Am I allowed to swap a shift?" (policy, cited from the handbook)
- "Build next week's schedule – Dana can't work Tuesday." (proposal)

### The handbook

An invented company **employee handbook** in markdown, about ten sections (overtime, breaks, sick days, shift swaps,
lateness, …). An ingestion script splits it by section, embeds each chunk and stores it in the database; the
`search_policy` tool embeds the question, ranks chunks by cosine similarity and returns the top matches with their
section titles for citation.

## 8. Out of scope for v1, and what comes next

**Out of scope:** real payments, taxes and deductions, multiple organizations, native mobile app, holiday calendar,
shift swaps between employees.

**Natural extensions** (each is designed for, none is built):

- weekly overtime on top of daily tiers;
- night and weekend premiums as additional pay rules;
- unpaid breaks;
- planned-vs-actual comparison per employee and week;
- persisted assistant conversations;
- a constraint-programming solver (e.g. OR-Tools CP-SAT) when teams grow beyond what backtracking handles well.

## 9. Quality bar

Four things are never compromised, whatever the deadline:

1. **Pay tests** – the full matrix in §5.4 passes before any pay change is merged.
2. **Scheduler tests** – no solution, tight solution and fairness cases pass before any solver change is merged.
3. **Authorization in services** – no endpoint or tool bypasses the service layer.
4. **The docs and plans trail** – every change starts from an approved plan and keeps the docs current.
