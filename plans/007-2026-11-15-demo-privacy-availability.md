# Plan 007 – Demo users, privacy and availability

| | |
|---|---|
| **Status** | approved |
| **Date** | 2026-11-15 |
| **Related docs** | [product-definition](../docs/product-definition.md) §5.1, §5.2, §5.5, §6.2; [glossary](../docs/glossary.md); [architecture](../docs/architecture.md) §5, §6.2, §6.4, §9; [testing-rules](../docs/rules/testing-rules.md) (scheduler matrix); [deployment](../docs/deployment.md) §10 |
| **Roadmap** | plan 007 of 007 |
| **Branch** | plan/007-demo-privacy-availability |

## Goal

Four product changes, built with the delegation, hooks and review that plan 006 made real: the seed has seven
demo employees so the demo week can be fully staffed and the eval personas have more company; an assistant
conversation is seen only by the person who had it and is forgotten on sign-out, Demo-user switch, session
expiry or New conversation; the Schedule board opens on the current week with next week one click (or one link)
away; and an unanswered availability counts as `available` until the employee marks otherwise, consistently in
the docs, the solver, its explanations, the assistant's `who_is_available` tool, the availability form and the
seed.

## Scope

### In

**A. Two more demo employees**

- `scripts/seed.py`: append `("Maya Cohen", "48.00")` and `("Itai Shapira", "36.50")` to `EMPLOYEES` (rates
  distinct from the five existing ones; appended, so the index-based cycles of existing demo users do not move
  and a re-run on an existing database adds only the two users, their availabilities and their time entries;
  idempotent by email as today). Emails `maya@` and `itai@shibutzim.example`.
- Everything that hard-codes the seeded team: README "Demo" (accounts), `client/.env.example` and
  `docker-compose.yml` (`VITE_DEMO_USERS`), `docs/deployment.md` line 174 (`gh variable set DEMO_USERS …`),
  `tests/services/test_seed.py` (counts 5 → 7, rates, emails), `evals/cases.py` `SEEDED_RATES` (+ `48.00`,
  `36.50`), `docs/architecture.md` §5 seed sentence if it states a count.
- Manual steps for Yosef, listed in Validation and **not** run by the agent: `gh variable set DEMO_USERS …`
  (then a redeploy picks it up) and `uv run python scripts/seed.py` against Supabase.

**B. Schedule board opens on the current week**

- `ScheduleBoard.tsx`: on mount load `currentWeekStart()`; honor `?week=YYYY-MM-DD` (a Sunday) so a link can
  open another week; `ProposalCard` "Open schedule" links to `/manager/schedule?week=<proposal week>`.
- `WeekNavigator` unchanged: "Next week" is the one click; "This week" appears when away from it.
- Workflow stays easy: open → this week (what is happening now, published) → "Next week" → Generate / Publish;
  from the assistant, the proposal's link opens the week it drafted.
- Tests: `ScheduleBoard.test.tsx` (`WEEK` becomes the current week of the frozen clock; new cases "opens on the
  current week", "Next week moves one week", "`?week=` opens that week"); `ProposalCard` link test.
- Docs: glossary "Schedule board" (opens on the current week; `?week=` selects another), product-definition §5.2
  manager flow sentence, architecture §9 (`ScheduleBoard` reads `week` from the URL), README caption line 44.

**C. Assistant conversations leak between users**

- Failing tests first (`qa`): `RootStore.test.ts` – after `auth.switchTo(other)` / `auth.logout()` /
  `auth.expireSession()` / a fresh `auth.login(...)`, `assistant.messages` is empty; `AssistantStore.test.ts` – a
  reply that arrives after `reset()` is dropped; `AssistantScreen.test.tsx` – New conversation is shown and
  clears; server `tests/api/test_assistant.py` – two users chatting in turn: the model sees only the history each
  request carried (fake LLM captures the prompt), and no route returns history (`GET /api/assistant/chat` → 405).
- Fix (`frontend`): `AuthStore` takes `onSessionCleared` and calls it from `clearSession()` (one point covers
  login, switch, logout, expiry); `RootStore` passes a callback that calls `reset()` on every per-user store
  (open question 3); `AssistantStore.reset()` also clears `isSending`, `isConfirming` and bumps a generation
  counter that `ask()` checks before applying a reply (same pattern as `ScheduleStore.requestId`). The
  conversation stays memory-only (never `localStorage`/`sessionStorage`), so a tab close or reload forgets it.
  "New conversation" exists (`AssistantScreen.tsx:113`); it stays, and is shown whenever there are messages.
- Docs: product-definition §5.5 line 137 (held by the client, memory only, cleared on sign-out, user switch,
  expiry and New conversation; never persisted in the browser), architecture §9 `AssistantStore` line, glossary
  "Assistant screen" (New conversation).

**D. No answer means `available`**

- Where the default lives: **inside the pure scheduler**, `constraints.is_workable(status)` becomes
  `status is not AvailabilityStatus.unavailable` (open question 4 gives the reasons). `solve.py:220` uses
  `.get`. Candidates are everyone active not marked `unavailable`; `preferred` keeps its scoring bonus; a
  `Block` (day off) still excludes whatever was answered.
- Tests first (`qa`), the scheduler matrix in testing-rules kept intact: `test_constraints.py` split
  (`None` workable, `unavailable` violates); `test_solve.py` cases rewritten so exclusion is explicit
  (`unavailable` rows instead of missing rows), `test_solve_no_answer_counts_as_available`, the random
  instances and the exhaustive-search comparison keep `None` in the status pool; `test_trace_explain.py`:
  non-answerers now appear in `excluded_by` with their real reason, people marked `unavailable` stay silent;
  `helpers.py` `WORKABLE` semantics; `test_schedule_service.py:71` ("only 1 available" becomes a filled shift);
  `test_assignment_service.py:243` (`no_answer` → no warning, `unavailable` → `availability_ignored`);
  `tests/api/test_schedules.py:364` (no warning for no answer); `test_debug_schedule.py:79,140` (wording);
  `test_assistant_manager_tools.py:46` (`who_is_available` returns a fourth group `no_answer`);
  `test_seed.py:156-200` (no assignment has an `unavailable` row; with 7 employees the seeded current week is
  fully staffed).
- Server (`backend`): `constraints.py`, `solve.py`, `explain.py` (docstring and `excluded_by`: "employees who
  marked unavailable are not listed"), `scoring.py` docstring (spread among all candidates), `assignment_service`
  warning text ("marked {when} unavailable"), `availability_service` and `models/availability.py` docstrings,
  `who_is_available` tool (+`no_answer` list of active employees without a row, counted as available) and its
  prompt `prompts/tools/who_is_available.md`, `role_manager.md` line 1, `scripts/debug_schedule.py` ("Marked
  unavailable:" and the lever sentence), `scripts/seed.py` comment line 84, handbook
  `server/handbook/employee-handbook.md:48-49` ("A shift you do not answer counts as available; mark the shifts
  you cannot work").
- Client (`frontend`): `AvailabilityStore` `DEFAULT_STATUS = 'available'` and docstring; `AvailabilityForm`
  text ("A shift you do not answer counts as available; mark the ones you cannot work"); tests
  `AvailabilityStore.test.ts:56-66,113-118,149` and `AvailabilityForm.test.tsx:80-92` flipped.
- Evals: `cases.py` `who_is_available` gains `expected_facts` on a name from the `no_answer` group of the seeded
  week (derived by hand from the seed cycle); run `--only who_is_available,…` at the end of the plan.
- Docs: product-definition §5.1 line 71 ("no answer counts as `available`; opting out is explicit"), §5.2 line
  83 ("never placed on a shift they marked `unavailable`"), §6.2 hard-constraint sentence; glossary
  "Availability status" (missing answer counts as `available`), "Score" (spread among candidates), "Explanation"
  example unchanged; architecture §5 data-model row 155 and §6.2; README caption line 52; `debug-schedule`
  SKILL.md lines 39, 49.
- Manual step for Yosef: re-run `scripts/ingest_handbook.py` (needs `GEMINI_API_KEY`) locally and against
  Supabase after the handbook text changes.

### Out

- Persisted conversations, a server-side history endpoint, conversation history on other devices.
- A distinct "not answered yet" visual state in the availability form (an unanswered shift shows as
  `available`, the default); a reminder to employees who have not answered.
- Changing `SchedulingRules.max_steps`, the solver algorithm, or fairness scoring beyond the docstring.
- Remembering the board's last visited week across screens (My shifts and the board keep loading their own
  default on mount, as today).
- New demo data beyond the two employees (no new templates, no new handbook sections).

## Assumptions

- Plan 006 is `done`: the scope guard, post-Bash checks and pre-commit hook exist and run.
- Verified in code (2026-11-15), the privacy bug: `AssistantStore` (`client/src/stores/AssistantStore.ts:40-53`)
  holds the conversation in memory only, has no user id, and is created once per tab by `RootStore` (L68);
  `App.tsx:17` keeps one `RootStore` for the tab's life. `AuthStore.login/switchTo/logout/expireSession` all go
  through `clearSession()` (L144-148), which clears only the token; no store is reset and nothing in
  `client/src` reacts to a user change. Hence: same tab + Demo-user switch → the next user sees the previous
  user's chat (the computer); a fresh load on the phone starts empty. The token is the only `localStorage` key
  (`tokenStorage.ts:10`). Server side: `POST /api/assistant/chat` is the only assistant route; the client sends
  the whole history; no table stores message text (`tool_call_logs` holds tool, args, user, duration, size,
  status) and no endpoint returns history. The server cannot return another user's history; it trusts the
  history the client sends.
- Verified, the board: `ScheduleBoard.tsx:63-67` loads `shiftWeek(currentWeekStart(), 1)` on every mount;
  `ScheduleStore` itself defaults to the current week; `WeekNavigator` already offers "Next week" in one click
  and shows "This week" when away from it. `ProposalCard.tsx:110` links to `/manager/schedule` with no week,
  so a confirmed next-week draft would open on the wrong week once the default changes. The server has no
  default week (`week_start` is always required).
- Verified, the availability rule: it is applied inside the pure scheduler, `constraints.is_workable(None) →
  False` (`scheduler/constraints.py:15-20`); `solve_week` (`schedule_service.py:159-195`) passes only existing
  rows. `solve.py:220` indexes `status[(shift_id, e)]` directly and would raise `KeyError` for a no-answer
  candidate. `assignment_service.py:180-205` and `scripts/debug_schedule.py:73-88` reuse the same predicate,
  so changing it in the scheduler changes the edit warning and the debug report consistently. The seed leaves
  20 of 80 (employee, shift) pairs per week unanswered; each seeded week needs 26 positions and 5 employees ×
  5 max shifts = 25, so today's seeded week can never be fully staffed; with two more employees it can.
- Verified: the evals and `test_seed.py` are the only tests that read seeded values; the service and API tests
  use the conftest's own users (`Mia Manager`, `Eli Employee`, `Dana Other`).
- Verified: the seed is "insert if missing by natural key, never update", so appending employees is idempotent
  and a re-run on an existing database does not touch the existing published schedule (it skips a week that
  already has one). On a fresh database the current week is generated with 7 employees and the new rule.
- Assumed: solver size stays small. Candidates per shift rise from ~50 % to ~75 % of employees on the seeded
  data; with 7 employees and 16 shifts the search budget is not reached. Validation measures it.
- Assumed: Yosef runs the manual production steps (seed on Supabase, `DEMO_USERS` variable, handbook
  re-ingest); the agent never touches the production database.

## Steps

Order: A (seed) → B (board) → C (privacy) → D (availability rule); the eval run comes last so one run covers
A and D.

1. **qa** – `test:` `test_seed.py` expects 7 employees, 7 distinct rates, the two new emails; `test_cases.py`
   / `SEEDED_RATES` expectations. Failing.
2. **backend** – `feat:` seed gains the two employees; `evals/cases.py` `SEEDED_RATES`; docs/config mirrors
   (README demo accounts, `client/.env.example`, `docker-compose.yml`, `docs/deployment.md`,
   architecture §5 if it states a count). Tests of step 1 pass.
3. **qa** – `test:` `ScheduleBoard.test.tsx` current-week default, "Next week", `?week=`; `ProposalCard` link.
   Failing.
4. **frontend** – `feat:` board default + `?week=`; proposal link; `WeekNavigator` untouched.
5. **main** – `docs:` glossary "Schedule board", product-definition §5.2, architecture §9, README caption.
6. **qa** – `test:` the privacy tests (client: `RootStore`, `AssistantStore`, `AssistantScreen`; server:
   two-user history test, no history route). Failing on the client side; the server tests pass and stay as the
   proof the server never returns anyone else's history.
7. **frontend** – `fix:` `AuthStore.onSessionCleared`, `RootStore` reset wiring, `AssistantStore` generation
   counter and full `reset()`.
8. **main** – `docs:` product-definition §5.5, architecture §9, glossary "Assistant screen".
9. **main** – `docs:` the availability rule in product-definition §5.1/§5.2/§6.2, glossary, architecture §5/§6.2,
   README caption, `debug-schedule` SKILL.md (docs before code, so the qa step derives expectations from the
   docs).
10. **qa** – `test:` scheduler unit tests (`test_constraints`, `test_solve`, `test_trace_explain`, `helpers`),
    then `test_schedule_service`, `test_assignment_service`, `test_schedules` (API), `test_debug_schedule`,
    `test_assistant_manager_tools`, `test_seed`. Failing where behavior changes.
11. **backend** – `feat:` scheduler (`constraints.py`, `solve.py`, `explain.py`, `scoring.py` docstring);
    `assignment_service` warning; `who_is_available` tool + prompt; `role_manager.md`; `debug_schedule.py`;
    seed comment; handbook text; model/service docstrings. Tests of step 10 pass.
12. **qa** – `test:` client availability tests flipped (`AvailabilityStore.test.ts`, `AvailabilityForm.test.tsx`).
    Failing.
13. **frontend** – `feat:` `AvailabilityStore` default and texts; `AvailabilityForm` copy.
14. **qa** – `test:` eval `who_is_available` gains `expected_facts`; run the evals `--only who_is_available,
    generate_schedule_draft, <the rate cases>` with a fresh seed (real model, quota-aware; one run).
15. **main** – Validation, "What changed vs. plan", close and merge.

## Validation

- `cd server && uv run pytest -q` → all pass; `uv run pytest tests/unit/scheduler -v` lists the no-answer cases
  by name (`…no_answer_counts_as_available`, `…unavailable_violates_availability`) and the matrix cases from
  testing-rules remain present.
- `cd client && npm run lint && npm run typecheck && npm test` → pass; the new tests are listed by name.
- Seed, fresh local database: `uv run python scripts/seed.py` twice → second run inserts nothing new (log says
  so); `psql`: 7 employees + 1 manager; the current week's published schedule has every shift fully staffed and
  no assignment whose availability row is `unavailable`; `generate` on next week returns `complete: true` and
  `unfilled: []`; the steps used are printed in "What changed vs. plan" (solver size check).
- Board, as the manager in the dev client with a frozen clock in tests and by eye: `/manager/schedule` opens on
  this week; "Next week" → next week in one click; `/manager/schedule?week=<next Sunday>` opens next week; the
  proposal card's "Open schedule" lands on the drafted week.
- Privacy, by hand in one tab: sign in as `noa@`, ask the assistant a question, switch to `omer@` via the
  Demo-user switch → the Assistant screen is empty; switch back to `noa@` → still empty; sign out and in → empty;
  New conversation clears; reload clears. By test: the `RootStore`/`AssistantStore` cases above.
- Availability form as `noa@` for a week with an unanswered shift: it shows `available`; choosing `available`
  does not enable Save; choosing `unavailable` does and persists.
- `who_is_available` through the assistant as `dana@`: the answer names who has not answered and says they
  count as available; the eval `who_is_available` passes with the new facts; the rate cases pass with
  `SEEDED_RATES` of seven.
- `scripts/debug_schedule.py` on a week with an unfillable shift prints "Marked unavailable:" and never "Did not
  answer available".
- Docs grep: `grep -rn "counts as unavailable" docs README.md server/handbook client/src .claude` → no matches.
- `python3 .claude/hooks/archive_conversation.py --audit` on this plan's sessions shows `backend`, `frontend`,
  `qa` calls and zero shell writes into source.
- **Manual, Yosef only, after merge and deploy**: `gh variable set DEMO_USERS --body "<seven + manager>"` then
  a redeploy; `uv run python scripts/seed.py` with `DATABASE_URL` pointing at Supabase (adds the two users);
  `uv run python scripts/ingest_handbook.py` against Supabase for the new handbook text.

## Rollback

- Code: `git revert` the plan's commits. No migrations (no schema change).
- Seed data: the two demo users can be deactivated with `PATCH /api/users/{id}` as the manager or deleted by
  SQL (`users` by email, then their `availabilities`, `time_entries`, `assignments`); the seed never updates
  existing rows, so the original five are untouched.
- Availability rule: reverting the code restores "missing means unavailable"; the handbook must be re-ingested
  with the reverted text; existing availability rows are unaffected (no data change, only interpretation).
- Board default and the privacy fix: code revert only.

## Amendment on approval

Yosef approved the plan with "implement plan 007" (2026-11-15): all eight open questions are answered as suggested.

## Open questions (each with a suggested answer)

1. **Two plans as suggested, or split item 8 into 008?**
   → *Suggested:* two plans. Section D is the biggest block but shares the seed and the eval run with A; one
   plan means one eval run and one review. The steps are ordered so 1–8 (A–C) could close on their own if
   needed, and D (steps 9–14) moves to 008 unchanged.
2. **Names and rates of the new demo employees?**
   → *Suggested:* Maya Cohen, 48.00 and Itai Shapira, 36.50: Israeli names like the rest of the team, emails
   from the first name as the seed does, rates distinct from all existing ones (needed by the rate evals'
   `must_not_contain`).
3. **On a user change, reset only `AssistantStore` or every per-user store?**
   → *Suggested:* every per-user store (`assistant`, `schedule`, `pay`, `team`, `time`, `availability`) via a
   `reset()` each, from one callback. The same leak pattern exists for pay and team data (the previous user's
   numbers render until the new load returns); one mechanism closes all of it, and the assistant case is the
   one with a test per trigger.
4. **Where is the no-answer default applied: service layer building the solver input, or inside the pure
   scheduler?**
   → *Suggested:* inside the scheduler (`is_workable`). The rule is a scheduling rule and the scheduler already
   owns the `None` case; the service passes only the rows that exist and stays unchanged; `assignment_service`
   (edit warnings) and `debug_schedule.py` call the same predicate, so one change keeps the warning, the trace
   and the report consistent; the scheduler matrix tests then document the product rule, which the filling-in
   alternative would hide in the service. Filling in `available` rows in the service would also create "answers"
   that no employee gave, which the trace and `who_is_available` would then misreport.
5. **What does "cleared when they leave the page" mean?**
   → *Suggested:* closing or reloading the tab (already true: memory only, never persisted; the plan keeps it
   that way and tests that no browser storage is written). Navigating inside the app keeps the conversation,
   because the proposal card links the manager to the Schedule board and back, and the same person is still
   signed in. Clearing on every screen change would make that flow lose the answer.
6. **Should `who_is_available` return the non-answerers?**
   → *Suggested:* yes, a fourth list `no_answer` described as "no answer yet; counts as available". Managers
   need it to know whom to ask; it keeps the tool honest about what was actually answered.
7. **Does `preferred` still beat a no-answer in scoring?**
   → *Suggested:* yes: `preferred` keeps the bonus; no answer is scored exactly like `available`.
8. **Solver budget: change `max_steps`?**
   → *Suggested:* no; measure first (Validation records the steps used on the seeded week). Only if the
   seeded week or the random-instance tests hit the budget does a follow-up raise it.

## What changed vs. plan

*(filled in when the plan is closed)*
