# Plan 004 – Assistant: tools, handbook retrieval, proposals and evals

| | |
|---|---|
| **Status** | done |
| **Date** | 2026-11-11 |
| **Related docs** | [product-definition.md](../docs/product-definition.md) §5.5, §6.2, §7 · [architecture.md](../docs/architecture.md) §3, §4, §6.4–§6.6, §7–§9, §11 · [glossary.md](../docs/glossary.md) "Assistant", "Scheduling" · rules: [coding](../docs/rules/coding-rules.md) ("Assistant code"), [error-handling](../docs/rules/error-handling-rules.md), [database](../docs/rules/database-rules.md), [testing](../docs/rules/testing-rules.md), [ui](../docs/rules/ui-rules.md), [design-system](../docs/design-system.md), [git](../docs/rules/git-rules.md) · subagents: backend, frontend, qa · skill: [new-endpoint](../.claude/skills/new-endpoint/SKILL.md) |
| **Roadmap** | plan 004 of 005 |
| **Branch** | plan/004-assistant-handbook-evals |

## Goal

A signed-in person opens the Assistant screen and asks, in plain language, about their shifts, hours, pay or the
company policy; a manager can also ask who is free for a shift, how many hours the team worked, and for next
week's schedule with a wish such as "Dana can't work Tuesday". The model never computes anything: it chooses among
tools that run the **same services as the UI, as the current user**, so it sees and does exactly what that user
could. Policy answers come from an invented employee handbook through pgvector retrieval and **cite the section
title**. The one write tool returns a **proposal**; the user confirms it in the UI and the confirmation calls the
normal REST endpoint. Every tool call lands in `tool_call_logs`. One `llm` interface hides the provider, every
automated test runs against a scripted fake, and a fixed set of fifteen evals runs the real model on demand to
guard prompts and tools.

## Scope

### In

1. **`llm` adapter** (`server/app/assistant/llm/`): plain data types (`Message`, `ToolDefinition`, `ToolCall`,
   `ChatResult`), an `LLM` protocol with `chat(system, messages, tools) -> ChatResult` and
   `embed(texts) -> list[list[float]]`, a scripted `FakeLLM` for tests, and a `GeminiLLM` built on the official
   `google-genai` SDK (the only new server dependency, open question 1). Settings: `GEMINI_API_KEY`,
   `ASSISTANT_CHAT_MODEL`, `ASSISTANT_EMBEDDING_MODEL` (768 dimensions, fixed by migration 0001),
   `ASSISTANT_MAX_STEPS`; all documented in `.env.example`. A missing key makes the assistant unavailable, not the
   server.
2. **Employee handbook** (`server/handbook/employee-handbook.md`, ten `##` sections consistent with the product's
   rules: overtime tiers, breaks, sick days, shift swaps, lateness, availability deadline, minimum rest, clocking in
   and out, corrections, pay day), `scripts/ingest_handbook.py` (split by `##`, embed through the adapter, replace
   the rows; re-running is idempotent), `handbook_repository` with a cosine-similarity query, and
   `handbook_service.search_policy` returning the top chunks with their section titles.
3. **"Blocked" hard constraint in the pure scheduler** (TDD): a `Block(employee_id, shift_id)` input excludes that
   person from that shift with its own `Constraint.blocked` reason in traces and unfilled-slot sentences. The
   service maps "user X is off day D" to the shifts that start on D (`Asia/Jerusalem`).
   `propose_schedule` and `generate_schedule` take an optional `unavailable: list[DayOff]`;
   `POST /api/schedules/{week_start}/generate` accepts an optional body `{"unavailable": [{"user_id", "day"}]}`.
   Without a body nothing changes, so the plan 003 board is untouched.
4. **Two service functions the tools need**, with authorization first: a person's assignments across weeks for a
   date range (employees see published schedules only), and the availability answers of one shift with names
   (managers only). Service tests only; no new REST endpoints for them.
5. **Tools** (`server/app/assistant/tools/`), one module each, a registry that filters by role, JSON-schema
   arguments validated with Pydantic, compact purpose-built results: `get_my_shifts(from, to)`,
   `get_my_hours(from, to)`, `explain_pay(from, to)`, `search_policy(query)` (both roles);
   `who_is_available(shift_id)`, `get_team_hours(from, to)`, `generate_schedule_draft(week_start, unavailable)`
   (managers). Domain errors and bad arguments come back to the model as structured error results; a tool called
   outside its role returns a refusal result even if a model somehow names it.
6. **Tool-call log**: a wrapper around every dispatch writes one `tool_call_logs` row (tool, args, user,
   duration, result size, status `ok` / `error` / `refused`), committed even when the tool failed. The table
   exists; no migration.
7. **Agent loop and prompts** (`assistant/agent.py`, `assistant/prompts/*.md`): system prompt from a file with
   the user's name, role, today's date and the Sundays of this and next week filled in; tool descriptions from
   files; role-filtered tool definitions; dispatch through the log wrapper; stop on a text answer or at
   `ASSISTANT_MAX_STEPS` with a polite "I could not finish" message; a clear refusal for anything outside the
   tools or the role; tool results and handbook text are treated as data, never as instructions.
8. **Chat endpoint** `POST /api/assistant/chat` (any signed-in user; follow `/new-endpoint`): body is the history
   (`user` / `assistant` text messages only, at most 20, each at most 2,000 characters); the response carries the
   answer text, the citations used, the tool calls made (names and arguments, for the UI and the evals), and an
   optional `proposal`. Provider failure or a missing key is the new `503 assistant_unavailable`. Stateless.
9. **Evals** (`server/evals/`): fifteen cases in `evals/cases.py` (question, role, expected tools, expected facts
   taken from the tool results of that run, required citation, or expected refusal), checkers, and a runner
   `uv run python -m evals.run` that calls the real model against the seeded development database and prints a
   pass / fail table with a non-zero exit on failure. The checkers are unit-tested with `FakeLLM`.
10. **Client**: `api/assistant.ts` with DTOs, `AssistantStore` (history, send, pending, error, proposal state,
    confirm through the schedules API), an **Assistant screen** at `/me/assistant` reachable from the navigation
    for both roles, message list with loading, error and empty states, citations under an answer, a proposal card
    with Confirm / Cancel that calls `POST /api/schedules/{week}/generate` with the proposal's constraints and then
    opens the board. Store and screen tests with the fake API.
11. **Docs and tooling**: architecture §4, §6.4–§6.6 and the decision log; glossary; error-handling catalogue;
    README and `AGENTS.md` command rows (`ingest_handbook.py`, `evals.run`); seed prints how to ingest the
    handbook; the `.claude/settings.json` change deferred from plan 003 is committed first (step 1).

### Out

- Persisted conversations, streaming answers, Markdown rendering of answers (plain text with line breaks).
- Any write tool other than `generate_schedule_draft`; the assistant never edits assignments, availability or
  time entries.
- A REST endpoint for "my assignments across weeks" or "answers for one shift" (service functions only).
- Shift swaps between employees, holiday calendar, Hebrew UI (the model may answer in the user's language).
- A vector index (`hnsw` / `ivfflat`): ten rows do not need one (open question 7).
- The MCP server, Dockerfile, CI, PWA (plan 005). Playwright tests (plan 005).
- Evals in CI: they cost money and need a key; plan 005 decides whether to run them on a schedule.
- A conversation view for managers of what employees asked (`tool_call_logs` has no UI).

## Assumptions

Verified:

- `handbook_chunks` (`vector(768)`) and `tool_call_logs` (`args` jsonb) exist since migration 0001; the models
  are in `app/models/`. No migration is needed.
- `schedule_service.propose_schedule` (dry run) and `generate_schedule` share `solve_week`, which is where
  blocks are added; the solver is deterministic for the same input and step budget, so a confirmed proposal
  re-solves to the same schedule.
- `pay_service.get_pay` / `get_team_pay`, `time_entry_service.list_time_entries`,
  `availability_service.list_availabilities` and `assignment_service` exist and take `current_user`.
- The test fixtures (`manager_client`, `employee_client`, `NOW`, `NEXT_WEEK`, factories) cover what the new
  tests need; the suite refuses non-`_test` databases.
- The client has a `RootStore`, an `ApiClient` with `ApiError`, `renderWithStores` / `makeFakeApi` helpers, a
  shell with role-split navigation, and the `ActionResult` pattern for user actions.
- `uv` 0.13.7 and Python 3.12.16 are installed; the server venv has no Google SDK yet.
- The working tree holds the plan 003 deferral (TypeScript hook registration and `npm` / `npx` allow rules in
  `.claude/settings.json`); it is committed as step 1 of this plan.

Not verified (stated as the plan's bets):

- A Gemini API key is available to Yosef for the eval runs and the browser checks. Without one every step still
  passes its tests; only validation items 14 and 16 need it.
- `google-genai` exposes function calling and `output_dimensionality=768` embeddings the way the adapter expects;
  the adapter's conversion code is unit-tested without network, and the eval run is the integration test.
- The default model names (`gemini-2.5-flash`, `gemini-embedding-001`) are current; they are settings, not code.

## Steps

Each step is one commit unless noted; tests precede the code they test (`test:` then `feat:`).

1. `chore: register the TypeScript post-edit hook and npm permissions` – commit the pending
   `.claude/settings.json` change (plan 003 deferral) and confirm by editing one `.tsx` file.
2. `chore: add google-genai and assistant settings` – dependency pinned, `Settings` fields, `.env.example` rows.
3. `test:` + `feat: llm adapter with a scripted fake and the Gemini implementation` – data types, protocol,
   `FakeLLM` (a queue of scripted replies and embeddings, records every call), `GeminiLLM` (message and tool
   conversion unit-tested; network only in evals), `get_llm()` dependency that raises `assistant_unavailable`
   without a key.
4. `docs: employee handbook` – `server/handbook/employee-handbook.md`, ten sections whose rules match
   product-definition §6 (tiers, Sunday weeks, 8 h rest, five shifts).
5. `test:` + `feat: handbook ingestion and policy search` – `handbook_repository.replace_all` /
   `search(embedding, k)` (pgvector `cosine_distance`), `handbook_service.search_policy(session, llm, query)`,
   `scripts/ingest_handbook.py` (idempotent, prints the section count). Tests use fake unit vectors so ranking is
   exact.
6. `test:` + `feat: scheduler blocked constraint` – `Block`, `Constraint.blocked`, forward-checking exclusion,
   trace entries and the explain sentence "… excluded: blocked by the manager"; mandatory matrix item: the
   constraint violated in isolation is never produced.
7. `test:` + `feat: generate and propose accept days off` – `DayOff(user_id, day)` in the service, day → shift
   mapping in `Asia/Jerusalem`, a 422 for a day outside the week or an unknown user, optional request body on
   `POST /api/schedules/{week_start}/generate` (401/403 matrix re-run with the body), schema docs.
8. `test:` + `feat: assignment range and shift answers services` – `assignment_service.list_for_user(from, to)`
   (employees see published schedules only; managers see drafts too) and
   `availability_service.list_for_shift(shift_id)` with names and statuses (managers only).
9. `test:` + `feat: tool registry, logging wrapper and employee tools` – registry with role filter, argument
   models, `call_tool(session, llm, user, name, args)` that times, logs and never raises; `get_my_shifts`,
   `get_my_hours`, `explain_pay`, `search_policy`.
10. `test:` + `feat: manager tools and the schedule proposal` – `who_is_available`, `get_team_hours`,
    `generate_schedule_draft` returning `Proposal { week_start, unavailable, summary, assignments, unfilled }`.
11. `test:` + `feat: agent loop and prompts` – `prompts/system.md`, `prompts/tools/<tool>.md`, template
    variables, step limit, refusal path, proposal extraction; tests drive the loop with `FakeLLM` scripts.
12. `test:` + `feat: POST /api/assistant/chat` – via `/new-endpoint`: 401, 422 for a bad history, 503 without a
    key, happy paths for a read answer, a citation and a proposal; `ServiceUnavailable` error class and code.
13. `test:` + `feat: evals runner and fifteen cases` – `evals/cases.py`, `evals/checks.py`, `evals/run.py`;
    checker unit tests with the fake; then one real run and its table pasted into "What changed vs. plan".
14. `test:` + `feat: assistant API client and store` – `api/assistant.ts`, types, `AssistantStore` with
    `send`, `confirmProposal`, `dismissProposal`, `reset`.
15. `test:` + `feat: Assistant screen` – route, navigation entry for both roles, message list, composer,
    citation list, proposal card, loading / error / unavailable states, phone layout at 375 px.
16. `docs: assistant architecture, glossary, commands and README` – architecture §4 layout and §6.4–§6.6 as built,
    decision-log rows (blocked constraint; proposal confirm re-solves; evals on demand), glossary rows (`Block`,
    `DayOff`, `assistant_unavailable`), `AGENTS.md` command table, README section "Assistant".
17. `plan: close plan 004` – validation results, "What changed vs. plan", roadmap `done`, merge into `main`.

## Validation

| # | Check | Expected |
|---|---|---|
| 1 | `git log --oneline` on the branch | the approval commit first; `chore` (settings) before any `feat`; every `feat` of a pure module preceded by its `test` |
| 2 | `cd server && uv run pytest -q` | all pass; the new tests include: scheduler matrix with `blocked` in isolation; service authorization for the two new functions; 401/403/422 for `generate` with a body; 401/422/503 and happy paths for `chat`; one `tool_call_logs` row per dispatched call including a failed and a refused one; ingestion run twice leaves the same row count |
| 3 | `uv run pytest tests/unit/scheduler -v` | the six mandatory scheduler cases still pass plus `test_solve_never_assigns_a_blocked_employee` |
| 4 | `uv run ruff check . && uv run ruff format --check . && uv run alembic check` | clean; "No new upgrade operations detected" |
| 5 | `grep -rn "app.repositories\|app.models" server/app/assistant/tools server/app/assistant/agent.py` | no output (tools call services only) |
| 6 | `grep -rln "You are" server/app/assistant/*.py server/app/assistant/tools/*.py` | no output; prompt text lives only under `assistant/prompts/` |
| 7 | `grep -rn "google" server/app --include=*.py -l` | only `app/assistant/llm/gemini.py` |
| 8 | `grep -rn "genai\|GeminiLLM" server/tests` | no output in unit, service or API tests (fake only) |
| 9 | Employee calls `POST /api/assistant/chat` with the fake scripted to request `get_team_hours` | the tool is absent from the definitions sent to the fake, and the forced call returns a `refused` result that is logged with status `refused` |
| 10 | `uv run python scripts/ingest_handbook.py` twice (real key) | prints "10 sections" both times; `SELECT count(*) FROM handbook_chunks` is 10 |
| 11 | `uv run python scripts/seed.py` | still idempotent; ends with the hint to run the ingestion script |
| 12 | API test: employee asks "Am I allowed to swap a shift?" with the fake scripted to call `search_policy` | the response's `citations` contains the handbook section "Shift swaps" and the text names it |
| 13 | API test: manager asks for next week with Dana off Tuesday | response has `proposal.unavailable == [{user_id: Dana, day: Tuesday}]`, no `schedules` row was created, and `POST /api/schedules/{week}/generate` with that body creates the draft with no Dana assignment on Tuesday |
| 14 | `uv run python -m evals.run` (real key, seeded dev database) | table of 15 cases; exit code 0 with all passing after at most one retry per case (open question 9); results pasted into the plan |
| 15 | `cd client && npm run lint && npm run typecheck && npm test && npm run build` | all exit 0; new tests cover the store (send, error, proposal confirm calls the schedules API) and the screen |
| 16 | Browser, 1280 px as Dana and 375 px as Noa (real key) | Noa: "How much overtime did I do this month?" answers with the number shown on My pay; "Can I swap a shift?" cites "Shift swaps"; the manager-only question is refused politely. Dana: "Build next week's schedule, Noa can't work Tuesday" shows a proposal card; Confirm opens the board with the draft and no Noa on Tuesday; Cancel leaves no schedule. No horizontal overflow at 375 px |
| 17 | Server started without `GEMINI_API_KEY` | every other screen works; the Assistant screen shows "The assistant is not available" from the 503 |

## Rollback

- Code: delete the branch before merge, or `git revert` the merge commit after.
- Dependency: `cd server && uv remove google-genai`; remove the four assistant variables from `.env.example`.
- Data: no migration. To clear what the plan writes: `DELETE FROM tool_call_logs; DELETE FROM handbook_chunks;`.
- Settings hook (step 1): revert the commit; the hook script itself stays, as in plan 003.
- The schedules `generate` body is optional, so the plan 003 client keeps working on the server of either side.

## Open questions (each with a suggested answer)

1. **Which provider SDK?**
   → *Suggested:* the official `google-genai` package, pinned, because the architecture chose Gemini for its free
   tier and this is Google's current SDK; the `LLM` protocol keeps an Anthropic or OpenAI adapter a one-file
   change later.
2. **Default models?**
   → *Suggested:* `gemini-2.5-flash` for chat and `gemini-embedding-001` with `output_dimensionality=768`,
   because both are inexpensive, support function calling / 768-dimensional output, and the names are settings
   that can change without code.
3. **How to model "Dana can't work Tuesday"?**
   → *Suggested:* a real hard constraint in the pure scheduler (`Block`, `Constraint.blocked`) with the service
   turning a day into that day's shifts, because the solver's explanation can then say "blocked by the manager"
   instead of lying that Dana was unavailable, and the matrix guarantees it is never violated. The alternative
   (rewriting her availability answers before solving) is simpler but produces misleading explanations.
4. **How does Confirm apply a proposal?**
   → *Suggested:* the client calls the existing `POST /api/schedules/{week}/generate` with the proposal's
   `unavailable` list, because the product says confirm reuses the REST endpoint and the solver is deterministic,
   so the stored draft equals the proposal. Posting the proposal's assignments verbatim would add a second write
   path to test.
5. **What does the history contain?**
   → *Suggested:* only `user` and `assistant` text messages (no tool calls or results), capped at 20 messages of
   2,000 characters, because the client already holds the texts it shows, tool results would bloat requests, and
   the loop re-fetches anything it needs; a question about "that" from a previous turn still works through the
   assistant's previous text answer.
6. **Where do the evals live and in what format?**
   → *Suggested:* a Python module (`evals/cases.py`) with a typed dataclass per case, no YAML dependency; expected
   facts are expressed as paths into that run's tool results (for example `explain_pay.total`) rather than literal
   numbers, because the seed's time entries move with the calendar.
7. **A vector index on `handbook_chunks`?**
   → *Suggested:* none, because pgvector scans ten rows exactly and faster than an approximate index; the decision
   log notes when to add `hnsw` (hundreds of chunks).
8. **Does the seed ingest the handbook?**
   → *Suggested:* no; the seed stays key-free and prints the command, because ingestion needs the provider and the
   seed must keep working offline and in tests.
9. **Pass threshold for the real-model eval run?**
   → *Suggested:* every case must pass, with one automatic retry per case, because the evals guard behavior; a
   case that fails twice is a prompt, tool or case bug to fix, not noise to accept.
10. **Where is the chat in the client?**
    → *Suggested:* a full screen at `/me/assistant` with a navigation entry for both roles, because it works on a
    phone without a new drawer component, matches the shell's existing pattern, and gives the proposal card room;
    a side drawer can be added later without changing the store.
11. **Should the response include the tool calls made?**
    → *Suggested:* yes, names and arguments only (no results), because the UI can show "Looked at: your pay for
    March" for trust, and the evals compare expected tools against the same field the client sees.
12. **Agent step limit and timeouts?**
    → *Suggested:* `ASSISTANT_MAX_STEPS=6` and a 30-second provider timeout, because a question needs at most two
    or three tool calls and the endpoint must not hang a worker.
13. **Prompt-injection guard beyond the prompt?**
    → *Suggested:* one eval only, in which a handbook chunk contains an instruction to reveal all salaries and
    the assistant must ignore it, because authorization already lives in services (a tool cannot leak what the
    user may not see), so the guard is defense in depth, not the line of defense.
14. **Commit the pending `.claude/settings.json` change in this plan?**
    → *Suggested:* yes, as step 1, because it is the plan 003 deferral, it already sits in the working tree, and
    it is a `chore` with no product effect.

## What changed vs. plan

**Outcome.** Every scope item is built and committed on the branch. The server has 980 tests and the client 193;
ruff, `alembic check`, the client lint, typecheck and build are clean. Yosef checked the screens in a browser and
they look good; the assistant itself answered "not available" there because the default model timed out, which led
to the lite model becoming the default. The plan is closed with the real-model checks deferred at Yosef's request
(see Deferred).

### Deviations

| What | Why | Effect |
|---|---|---|
| `google-genai` is pinned to **2.33.0**, not the newest 3.2.0. | 3.2.0 was published the day it was installed; plan 003's rule is a release at least two weeks old. | `server/pyproject.toml`. |
| The chat model default is **`gemini-3.1-flash-lite`**, not `gemini-2.5-flash`. | The API says 2.5 is no longer available to new users; `gemini-3.8-flash` timed out on every call and `gemini-3.5-flash` timed out when Yosef opened the app. The lite model answered all 12 calls. | One setting in `config.py` and `.env.example`. |
| The free tier allows **5 requests a minute and 20 a day per model**. Evals space calls **13 s** apart, cap at 80 calls, and **retry a failing case only with `--retries`** (default 0). | Found in the first real run; Yosef asked for careful use of the quota. Open question 9 had suggested one automatic retry. | A provider error stops the run at once and spends nothing more. |
| `embed(texts, task)` takes a document or query task. | The provider embeds a question differently from a document. | `EmbedTask`; the fake records it. |
| `who_is_available` takes a **day and an optional shift name**, or a `shift_id`. | The model cannot know shift ids, so "who can work Tuesday morning?" had no way to be answered. | `shift_service.get_shift` was added. |
| Days off are matched by **name** in the draft tool, through `user_service.find_active_employee`. | The model never sees ids it could invent. | Ambiguous names return an error asking which one. |
| A write tool's proposal travels beside the model's result (`ToolOutcome.proposal`). | The model needs a short summary, the UI needs the details. | Documented in architecture §6.5. |
| `dispatch.py`, `context.py`, `formatting.py` and `chat.py` sit in `assistant/`, outside `tools/`. | Keeps `tools/` and `agent.py` free of model and repository imports (validation 5). | `User` is re-exported by `context.py` for type hints. |
| `pay_service.range_bounds` now calls a shared `weeks.day_range_bounds`. | The assignment service needed the same day-range rule. | No behavior change; pay tests pass. |
| The Assistant screen uses a plain two-row textarea, not an autosizing one. | Mantine's autosize needs browser APIs jsdom lacks. | Simpler, and testable. |
| The employee bottom bar has **four** items. | The Assistant is reachable for both roles. | Design system §4 and §6.4 updated. |
| Added a `docs:` row for `assistant_unavailable`, a seed hint, a README section and eval architecture §6.7. | Part of the plan's docs step. | |
| The TypeScript hook was checked by running its script directly. | I edited files through the shell, which hooks do not see. | It formats and lints a `.tsx` file and exits 0. |

### Validation results

| # | Result |
|---|---|
| 1 | The approval commit came first, `chore` settings before any `feat`, and each pure-module `feat` followed its red `test:`. |
| 2 | `uv run pytest -q`: 980 passed. Tests cover blocked in isolation, service authorization for both new services, 401, 403 and 422 for generate with a body, 401, 422 and 503 and the happy paths for chat, one log row per call including failed and refused ones, and ingestion twice. |
| 3 | Scheduler matrix: 202 passed, including the blocked cases and a random cross-check with blocks against exhaustive search. |
| 4 | `ruff check`, `ruff format --check` clean; `alembic check` reports nothing to do. |
| 5 | `grep app.repositories|app.models` over `assistant/tools` and `agent.py`: no output. |
| 6 | No prompt text in Python: the prompts and tool descriptions are the markdown files under `assistant/prompts/`. |
| 7 | `google` is imported only by `app/assistant/llm/gemini.py`. |
| 8 | No test imports the Gemini SDK except the adapter's own unit tests with a stub client. |
| 9 | A forced call to a manager tool by an employee returns a refused result and a `refused` log row (dispatch and agent tests). |
| 10 | `scripts/ingest_handbook.py` run twice against the real API printed "10 sections" both times; `handbook_chunks` holds 10 rows. |
| 11 | The seed ends with the hint to ingest the handbook; its tests pass. It was not re-run against the development database. |
| 12 | API test with the scripted fake: `search_policy` for a swap question gives the citation "Shift swaps" and the text names it. |
| 13 | API test: a manager's request returns a proposal with the day off, creates no schedule row; the generate tests with a body keep the person off that day. |
| 14 | **Partly.** Run 1 and 2 on `gemini-3.5-flash`: 8 cases passed (hours, overtime, pay, shifts, four policy cases), `pay_vs_last_month` failed on a brittle checker (fixed since), and the daily quota ended the run. A later run of the other seven on `gemini-3.1-flash-lite` passed 7 of 7, 11 model calls. No single run on one model has passed all fifteen yet. |
| 15 | Client lint, typecheck, build and 193 tests pass. |
| 16 | **Not run.** No browser tool was available. The chat endpoint, tools and proposal were exercised by the evals; the screen by component tests. |
| 17 | API test: without a key chat answers 503 `assistant_unavailable`. The other screens were not opened in a browser. |

### Deferred

- **Real-model eval run.** Eight cases passed on `gemini-3.5-flash` (before its daily quota ended) and seven on
  `gemini-3.1-flash-lite`; no single run has passed all fifteen on the lite default. Run it when the quota allows:
  `cd server && uv run python -m evals.run` (about 40 calls; the free tier allows 20 a day per model, so use
  `--only` in batches).
- **Chat in the browser with the real model**, including Confirm and Cancel on a proposal, as Noa at 375 px and as
  Dana at 1280 px. Yosef reviewed the screens; the chat answers were not seen because of the timeouts above.
