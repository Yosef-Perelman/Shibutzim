# Plan 002 – Shifts, availability and the scheduler

| | |
|---|---|
| **Status** | done |
| **Date** | 2026-11-11 |
| **Related docs** | [product-definition.md](../docs/product-definition.md) §5.1, §5.2, §6.2, §6.3 · [architecture.md](../docs/architecture.md) §3, §5, §6.2, §11 · [glossary.md](../docs/glossary.md) §2 "Scheduling", §3 · rules: [coding](../docs/rules/coding-rules.md), [database](../docs/rules/database-rules.md), [error-handling](../docs/rules/error-handling-rules.md), [testing](../docs/rules/testing-rules.md), [git](../docs/rules/git-rules.md) · skills: [new-endpoint](../.claude/skills/new-endpoint/SKILL.md) |
| **Roadmap** | plan 002 of 005 |
| **Branch** | plan/002-shifts-availability-scheduler |

## Goal

At the end of this plan the weekly cycle of architecture §6.2 runs end to end over REST: a manager defines shift
templates and generates a week's shifts; employees answer availability for next week; the manager clicks
**Generate** and gets a draft from a pure, exhaustively tested backtracking solver that never violates a hard
constraint, optimizes fairness and preferences, and names the reason for every slot it could not fill; the manager
corrects the draft (overlap and minimum rest are rejected, everything else warns) and publishes it, at which point
employees see it. The solver has a trace mode, and the `debug-schedule` skill uses it to explain an unfillable
week. Every service takes `current_user` and is ready to be called by the assistant tools of plan 004 without
changes.

## Scope

### In

1. **Shift templates** (managers): `GET /api/shift-templates`, `POST`, `PATCH /api/shift-templates/{id}`. A
   template is deactivated with `is_active = false`, never deleted (shifts reference it with `RESTRICT`).
2. **Weekly shift generation**: `POST /api/shifts/generate` (managers) creates the missing shifts of one week from
   the active templates, snapshotting times and `required_staff`, computing local times in `Asia/Jerusalem` and
   storing UTC; re-running adds only what is missing. `GET /api/shifts?week_start=` for any signed-in user.
3. **Availability**: `GET /api/availabilities?week_start=&user_id=` (own, or anyone / everyone for a manager) and
   `PUT /api/availabilities` upserting a whole week's answers at once; a missing answer stays `unavailable`.
   Employees can answer until the manager generates the schedule and never for a past week.
4. **Pure scheduler** (`server/app/scheduler/`, TDD): `solve(shifts, employees, availabilities, rules,
   trace=False) -> ScheduleResult` as a backtracking CSP with forward checking (architecture §11); hard
   constraints, soft scoring, a deterministic search budget, unfilled slots with structured reasons, a trace mode,
   and `explain()` turning a result into sentences like "Tuesday 07:00 needs 3, only 2 available; Dana excluded by
   minimum rest". The mandatory matrix of testing-rules plus boundary cases.
5. **Schedules** (managers unless said otherwise): `POST /api/schedules/{week_start}/generate` (creates or
   replaces the draft, never a published schedule; also usable in dry-run mode by services),
   `GET /api/schedules/{week_start}` (employees see only published), `POST /api/schedules/{week_start}/assignments`,
   `PATCH /api/schedules/{week_start}/assignments/{id}` (replace the employee), `DELETE .../assignments/{id}`,
   `POST /api/schedules/{week_start}/publish`.
6. **Scheduling rules in configuration**: `SchedulingRules(min_rest_hours=8, max_shifts_per_week=5, max_steps)`
   built by `Settings`, documented in `.env.example`.
7. **Seed**: availability for the current week too, and a **published** schedule for the current week produced by
   the solver; next week stays unscheduled so the demo can click Generate. Seed tests updated.
8. **Docs**: new glossary terms and error codes, `.env.example`, AGENTS.md command for the scheduler matrix.
9. **`debug-schedule` skill** (`.claude/skills/debug-schedule/SKILL.md`) backed by
   `server/scripts/debug_schedule.py`, which loads a week from the development database, runs the solver in trace
   mode and prints what blocks what and what the manager could relax.

### Out

- Any client code or design system (plan 003); assistant tools, the `generate_schedule_draft` proposal and
  "extra constraints" such as "Dana can't work Tuesday" (plan 004) – the generate service accepts `dry_run` now so
  plan 004 only adds the tool.
- Deleting shifts or schedules, un-publishing, a re-publish step, notifications when a schedule is published.
- Shift swaps between employees initiated by employees (product-definition §8), a holiday calendar.
- Minimum rest across the **week boundary** (the previous week's Saturday night vs. this Sunday morning) – see open
  question 7.
- Managers as assignable staff: the solver and manual edits place active **employees** only.
- Storing the solver's explanation or score in the database; the generate response carries them and the
  `debug-schedule` skill recomputes them.
- OR-Tools or any other solver dependency; time-of-day premiums; weekly overtime.

## Assumptions

Verified in the repository on 2026-11-11:

- All six scheduling tables exist from migration `0001` with the constraints of architecture §5: `shifts` unique
  `(template_id, week_start)` and `ends_at > starts_at`; `availabilities` unique `(shift_id, user_id)`;
  `schedules.week_start` unique; `assignments` unique `(schedule_id, shift_id, user_id)` with cascading deletes from
  `schedules` and `shifts`. `AvailabilityStatus` and `ScheduleStatus` enums exist. **No migration is expected.**
- `app/core/time.py` has `week_start`, `weekday_sunday_based`, `day_bounds`; `scripts/seed.py` has a private
  `local_to_utc` and already computes shifts from templates (the generation logic to lift into a service).
- The layer pattern, fixtures (`session`, `manager_client`, `employee_client`, `other_employee_client`, `NOW`),
  the error catalogue in `app/core/errors.py` and the `/new-endpoint` skill are in place from plan 001.
- The seed's week (16 templates → 16 shifts, 26 slots, 5 employees) is a realistic solver load; the seed test
  currently asserts counts 6 / 16 / 32 / 60 / 128, which step 12 changes.
- `uv`, Docker and the database on host port 5433 work as documented in AGENTS.md.

Not verified (taken as true):

- Backtracking with forward checking and a step budget fills a 7-day, 3-shift, 3-staff, 12-employee week in well
  under a second in CPython; the stress case in the validation checks it.
- Plan 003's "my shifts" screen can be served by `GET /api/schedules/{week_start}` filtered on the client; if it
  needs a cross-week "my assignments" query, plan 003 adds it (open question 9).

## Steps

Each step is one commit unless two are listed; `test:` commits are red when made and green after the matching
`feat:` commit. Endpoint steps follow `/new-endpoint`; the scheduler steps follow testing-rules "tests first".

1. **Time helper** – `test:` then `refactor:`: move the seed's `local_to_utc` into `app/core/time.py` as
   `local_to_utc(day, at, tz)` with unit tests (a normal day, the spring-forward and fall-back days, an end time at
   or before the start meaning next day via a `shift_bounds(day, start_time, end_time, tz)` helper). The seed uses
   the helper; behavior unchanged.
2. **Scheduler types and rules** – `feat:` `scheduler/types.py` (`Shift`, `Employee`, `Availability`,
   `Assignment`, `Exclusion`, `UnfilledSlot`, `TraceEvent`, `ScheduleResult`, all frozen dataclasses with
   timezone-aware datetimes) and `scheduler/rules.py` (`SchedulingRules` with validation; `default()`). Pure: the
   module imports only the standard library. `Settings.scheduling_rules` reads
   `SCHEDULER_MIN_REST_HOURS`, `SCHEDULER_MAX_SHIFTS_PER_WEEK`, `SCHEDULER_MAX_STEPS`; `.env.example` documents
   them.
3. **Hard constraints** – `test:` then `feat:` `scheduler/constraints.py`: `overlaps(a, b)` (half-open
   intervals), `rest_between(a, b)`, `violations(candidate_shift, employee_shifts, rules) -> list[Exclusion]`
   naming the constraint and the conflicting shift. Boundary tests: shifts touching end-to-start do not overlap;
   rest of exactly 8 h passes, 7 h 59 min fails; a 5th shift passes, a 6th fails; an availability of `unavailable`
   or no answer excludes.
4. **Solver** – `test:` then `feat:` `scheduler/solve.py` and `scheduler/scoring.py`. Variables are slots (one per
   required position of each shift); the domain of a slot is the employees who answered `available` or `preferred`
   and are not excluded by a hard constraint given the partial assignment. Order slots by smallest domain, break
   ties by earliest shift; order candidates by `preferred` first, then fewest assigned hours. After each
   assignment, forward checking removes the employee from the domains of overlapping shifts, shifts inside the
   rest window and, once at the cap, every remaining shift. A slot whose domain is empty is left **unfilled** and
   its exclusions are recorded; the search continues and backtracks only to improve the objective. The objective
   is lexicographic: most filled slots, then the soft score of `scoring.py` (preferred assignments honored minus
   the spread of hours across employees). The search stops at the first complete solution that fills every slot
   with no fairness debt, or when `max_steps` is exhausted, and returns the best found with `steps_used` and
   `complete`. The mandatory matrix, each case named after testing-rules: no solution (reports unfilled slots with
   reasons), tight solution, fairness, five "never violated" cases (availability, required staff, overlap, minimum
   rest, max shifts per week), preferred honored when possible; plus: deterministic output for equal input, budget
   exhaustion returns the best partial result, zero shifts, zero employees, a shift crossing midnight, DST week.
5. **Trace and explain** – `test:` then `feat:`: `trace=True` records a `TraceEvent` per eliminated candidate and
   per backtrack; `scheduler/explain.py` turns `UnfilledSlot`s (with `Employee.name` and the local time of the
   shift) into the product's sentences. Tests assert exact strings for the documented example.
6. **Shift templates** – `test:` then `feat:` via `/new-endpoint`: schemas (`ShiftTemplateCreate`, `Update`,
   `Out`), repository, `shift_template_service` (`ensure_manager` first), router. Pydantic validates
   `weekday` 0–6, `required_staff ≥ 1`, non-empty `name`; `end_time <= start_time` is legal and means next day.
   New codes: `shift_template_not_found` (404).
7. **Shifts** – `test:` then `feat:`: `shift_service.generate_shifts(session, current_user, week_start)` builds
   missing shifts from active templates with the step 1 helper, inside a nested transaction so a race on the
   unique constraint reports the row as already present; `list_shifts(session, current_user, week_start)` for
   everyone. `week_start` must be a Sunday (422 `invalid_week_start`). Response of generate: the full list of the
   week's shifts plus `created` count. The seed calls the same service-free helper, so the seed's own shift code
   shrinks.
8. **Availability** – `test:` then `feat:`: `availability_service.list_availabilities` (own; a manager may pass
   `user_id` or omit it for the whole team) and `set_availabilities(current_user, week_start, items)` upserting
   `(shift_id, status)` pairs for the current user, or for `user_id` when a manager. Rules: every shift must belong
   to `week_start` (422 `shift_not_in_week`); employees are refused when a schedule exists for the week or the week
   is in the past (409 `availability_locked`); managers are never locked.
9. **Schedule generate and read** – `test:` then `feat:`: `schedule_service.generate(session, current_user,
   week_start, *, dry_run=False)` loads shifts, active employees and availabilities, maps them to scheduler types,
   calls `solve`, and when not dry-run replaces the draft's assignments in one transaction (409
   `schedule_published` if the week is published, 422 `no_shifts_for_week` if the week has no shifts). Response
   `ScheduleGenerateOut`: the schedule, assignments, `unfilled` (shift, position, reasons, sentence) and `score`.
   `get_schedule(session, current_user, week_start)`: managers read any status; employees get 404
   `schedule_not_found` for a missing **or draft** schedule (a draft's existence is not theirs to see). `ScheduleOut`
   lists assignments with user name and shift times and `unfilled_count` per shift derived from `required_staff`.
10. **Assignment edits** – `test:` then `feat:`: `add_assignment(week_start, shift_id, user_id)`,
    `replace_assignment(week_start, assignment_id, user_id)`, `remove_assignment(week_start, assignment_id)`.
    Overlap and rest are checked with `scheduler.constraints` against the employee's other assignments in that
    schedule: 409 `shift_overlap`, 409 `min_rest_violation`. Duplicate → 409 `already_assigned`; unknown ids →
    404 `shift_not_found`, `assignment_not_found`, `user_not_found`; a deactivated or non-employee user → 422
    `user_not_assignable`. Soft rules return `warnings` in the body with codes `availability_ignored`,
    `max_shifts_exceeded`, `shift_overstaffed`. Edits work on drafts and published schedules alike.
11. **Publish** – `test:` then `feat:`: `publish(week_start, now)` sets `published` and `published_at = now`;
    409 `schedule_published` if already published; 404 if there is no schedule.
12. **Seed** – `feat:`: availability for the current week (same deterministic cycle), then
    `schedule_service.generate` + `publish` for the current week when no schedule row exists; counts in
    `tests/services/test_seed.py` updated and a test that the seeded schedule violates no hard constraint.
13. **Docs** – `docs:`: glossary (`Exclusion`, `Trace event`, `Warning`, `Dry run`, `Search budget`,
    `Availability lock`), error-handling table (all codes above), architecture §6.2 wording if anything moved,
    AGENTS.md commands (`uv run pytest tests/unit/scheduler -v`, `debug-schedule`).
14. **`debug-schedule`** – `chore:`: `server/scripts/debug_schedule.py --week YYYY-MM-DD [--min-rest H]
    [--max-shifts N]` runs the solver with `trace=True` on the development database and prints unfilled slots with
    their sentences, per-employee eliminations and a "what to relax" section (which constraint, if dropped, frees
    the most candidates). The skill tells the agent how to run it, how to read the output and what never to
    suggest (ignoring availability silently). Validated on the seeded week with one template's `required_staff`
    raised so the week cannot be filled.
15. **Close** – run the validation, fill "What changed vs. plan", `plan: close plan 002`, merge into `main`.

## Validation

All commands run from `server/` unless noted; the database is up (`docker compose up -d db` at the repo root).

| # | Check | Command / action | Expected |
|---|---|---|---|
| 1 | Whole suite | `uv run pytest -q` | all pass; count grows from 276 by the new service, API and unit tests |
| 2 | Scheduler matrix by name | `uv run pytest tests/unit/scheduler -v` | the ten testing-rules cases pass by name: no solution, tight solution, fairness, availability / required staff / overlap / minimum rest / max shifts never violated, preferred honored, plus the extra cases |
| 3 | Pure module | `grep -rE "sqlalchemy\|fastapi\|app\.(db\|repositories\|services\|models)\|datetime\.now" app/scheduler/` | no matches |
| 4 | Lint | `uv run ruff check . && uv run ruff format --check .` | clean |
| 5 | No schema drift, no migration | `uv run alembic check`; `ls alembic/versions` | "No new upgrade operations detected"; still only `0001` |
| 6 | Authorization matrix | the parametrized 401 and 403 tests in `tests/api/` | every one of the 14 protected operations returns 401 without a token; every manager-only operation returns 403 for an employee; an employee reading another's availability gets 403; an employee reading a draft gets 404 |
| 7 | Seed idempotent | `uv run python scripts/seed.py` twice | second run creates 0 rows; a `schedules` row for the current week with status `published` and assignments that `tests/services/test_seed.py` proves violate no hard constraint |
| 8 | Smoke test over HTTP | `uv run fastapi dev app/main.py`, then curl as the seeded manager: `POST /api/shifts/generate` for next week → shifts; `POST /api/schedules/{next}/generate` → draft with assignments and an `unfilled` list whose sentences read like product-definition §5.2; `POST .../assignments` with an overlapping shift → 409 `shift_overlap`; one inside 8 h → 409 `min_rest_violation`; one the employee marked `unavailable` → 201 with warning `availability_ignored`; `POST .../publish` → `published`; second publish → 409 `schedule_published` | as listed |
| 9 | Employee view | as a seeded employee: `GET /api/schedules/{next}` before publish → 404 `schedule_not_found`; after publish → the schedule; `PUT /api/availabilities` for a week with a schedule → 409 `availability_locked` | as listed |
| 10 | Solver speed | unit test with 7 days × 3 shifts × 3 staff and 12 employees with mixed answers | fills every slot in under 1 s wall time and within the default `max_steps`; the seeded week solves in under 0.2 s |
| 11 | Trace mode | unit test on the product's example (Tuesday 07:00 needs 3, two available, Dana excluded by rest) | `explain()` returns exactly "Tuesday 07:00 needs 3, only 2 available; Dana excluded by minimum rest" |
| 12 | `debug-schedule` | raise `required_staff` of the seeded Sunday morning template to 6, `uv run python scripts/debug_schedule.py --week <current>`; then `/debug-schedule <current week>` | the script names the shift, the shortfall and each excluded employee's reason and suggests what to relax; the skill reports the same in prose and changes no data |
| 13 | Docs trail | `git log --oneline main..plan/002-shifts-availability-scheduler` | reads docs → plan → tests → code; every error code in the handler table and in `ErrorCode` |

## Rollback

- **Code**: the plan is a branch until it closes; `git branch -D plan/002-shifts-availability-scheduler` discards
  it. After the merge, `git revert -m 1 <merge commit>` on `main`.
- **Schema**: none is changed, so no migration to downgrade.
- **Data**: the only new rows are a seeded schedule and its assignments and the current week's availability on
  the development database; `DELETE FROM assignments; DELETE FROM schedules;` and
  `DELETE FROM availabilities WHERE shift_id IN (SELECT id FROM shifts WHERE week_start = <current week>)`
  restore the plan 001 state. Templates and shifts created through the API remain valid without this plan's code.
- **Configuration**: the three `SCHEDULER_*` variables are optional with defaults; removing them changes nothing.

## Open questions (each with a suggested answer)

1. **Solver algorithm and budget: hand-written backtracking with a step budget, or OR-Tools CP-SAT with a time
   limit?**
   → *Suggested:* backtracking with forward checking and a deterministic `max_steps` budget (default 200 000
   search steps), because the decision log (architecture §11) already chose it for explainability, a step budget
   keeps the pure module clock-free and the tests reproducible, and the product's "time limit" is honored in
   spirit: the service can also pass a `deadline` callback later. No new dependency.
2. **Objective: how are "fair hours" and "preferred" weighed?**
   → *Suggested:* lexicographic – fill the most slots first; among equal coverage, score = `preferred_count ×
   PREFERRED_WEIGHT − hours_spread`, where `hours_spread` is the max minus min assigned hours across employees who
   answered at all. The weights live in `scoring.py` as named constants, not in `SchedulingRules`, because v1 has no
   UI to edit them and tests need fixed values. Spread beats variance because managers reason in "who got the most
   and least".
3. **Who is "the staff" for the solver and for manual edits?**
   → *Suggested:* active users with role `employee` in both cases; managers are not placed. One rule for both
   paths keeps "my shifts" unambiguous and avoids a manager silently becoming staff; a manager covering a shift is
   a plan 003+ decision.
4. **Manual edits: which rules block and which warn?**
   → *Suggested:* overlap and minimum rest block (409), exactly as product-definition §5.2 says; availability,
   max shifts per week and exceeding `required_staff` warn (`warnings` in the response). The product names only
   two blocking rules; the manager may know more than the system about the others.
5. **"Swap": a replace on one assignment, or an atomic exchange of two?**
   → *Suggested:* `PATCH .../assignments/{id}` replacing the employee, validated like an add. A two-way exchange
   is two calls; an atomic exchange endpoint can be added when the schedule board shows it is needed.
6. **Availability lock: when may an employee no longer answer?**
   → *Suggested:* when a schedule row exists for the week (draft or published) or the week is already past;
   managers are never locked. This is the product's "until the manager generates the schedule"; past weeks are
   read-only per §5.1. A manager who regenerates after new answers simply clicks Generate again.
7. **Minimum rest across the week boundary.**
   → *Suggested:* out of scope for v1 and documented as a limitation in the glossary entry for minimum rest. The
   solver sees one week; handling it needs the previous week's published assignments as fixed context, which is a
   small follow-up once the basic cycle is proven.
8. **Scheduling rules from the environment, or code defaults only (as plan 001 did for pay tiers)?**
   → *Suggested:* environment variables with defaults, because product-definition §5.2 explicitly says minimum rest
   is configurable, and `debug-schedule` wants to show "what if rest were 7 h" without a code change.
9. **A cross-week "my assignments" endpoint now?**
   → *Suggested:* no. `GET /api/schedules/{week_start}` with client-side filtering serves the "my shifts" screen;
   plan 003 adds `GET /api/assignments?user_id=&from=&to=` through `/new-endpoint` if it needs it.
10. **Generate when the week has no shifts: auto-generate shifts, or fail?**
    → *Suggested:* fail with 422 `no_shifts_for_week`. Generating shifts is the manager's explicit step (it
    snapshots templates), and a silent side effect would surprise the availability lock.
11. **Should GET schedule carry unfilled reasons?**
    → *Suggested:* no; it carries `unfilled_count` per shift (derived). Reasons are returned by generate and
    recomputed by `debug-schedule`. Storing them would need a migration and a JSON column for data that goes stale
    on the first manual edit.
12. **Seed a published schedule for the current week?**
    → *Suggested:* yes, by running the real solver inside the seed (idempotent: skipped when the row exists). The
    pay page and "my shifts" of plan 003 need a published week on first run, and it is a free end-to-end test of the
    solver on realistic data.
13. **Week identification in paths: `{week_start}` as a date in the URL, validated as a Sunday?**
    → *Suggested:* yes, `YYYY-MM-DD` and 422 `invalid_week_start` when it is not a Sunday, matching the glossary's
    `/api/schedules/{week_start}` and keeping one vocabulary across shifts, availability and schedules.

## Amendment on approval

Approved by Yosef on 2026-11-11 with every open question answered as suggested. No changes to scope.

## What changed vs. plan

**Outcome.** Every goal item shipped: 31 commits on `plan/002-shifts-availability-scheduler` (this one included),
670 tests passing (149 in the scheduler unit suite), all validation items run (results below). All thirteen open
questions were approved as suggested. No migration and no new dependency were needed.

### Deviations

| What | Why | Effect |
|---|---|---|
| The solver stops at the first assignment that reaches the optimistic coverage bound, then runs a hill-climbing polish; the plan's "no fairness debt" stop rule was dropped. | A proof of optimal fairness is not cheap. Branch and bound on coverage plus a polish that only ever improves a valid schedule is simpler and cannot break a hard constraint. | Documented in the solver docstring, glossary ("Solver") and architecture §11. Default budget stays 200 000 steps; the seeded week proves its optimum in 222 steps. |
| The first dive always finishes even if the budget is tiny, so `solve` always returns a valid schedule; `steps` can then exceed `max_steps`. | A budget that could stop before any solution exists would return nothing. | `complete` says whether the search finished. |
| `UnfilledSlot` is **per shift** (`required`, `assigned`, `missing`, `reasons`), not per position. | One entry per missing position repeated identical reasons. | Glossary updated; the API's `unfilled` items carry `shift_id`, `required`, `assigned`, `missing`, `reasons`, `sentence`. |
| Dry run is `propose_schedule(..., rules=None, trace=False)`, a separate function, instead of `generate(..., dry_run)`. | No optional return type in the REST path; the same function serves `debug-schedule` and the future assistant tool. | `generate_schedule` calls the same solve helper. |
| Assignment edits live in `assignment_service`; small shared helpers in `services/users.py` and `services/weeks.py`; `Shift` got a `template` relationship and a `name` property. | Keeps each service file focused; the shift list needs the template name. | No schema change (`alembic check` clean). |
| The 401 / 403 tests for the assignment and publish routes arrived in steps 10 and 11, not step 9; the 403 matrix sends valid bodies. | The routes did not exist at step 9; a bodyless call reaches validation (422) before authorization. | Same coverage in the end. |
| The seed's own shift insertion did not shrink onto a service helper; it only shares `shift_bounds`. | The seed counts created versus existing rows per shift. | Behavior unchanged. |
| Validation 6 said 14 protected operations; there are 13. | Miscount in the plan. | All 13 have a 401 test; every manager-only one has a 403 test. |
| Validation 12 ran on the **seeded** next week (26 positions, 21 filled) instead of raising a template's `required_staff`. | Shifts snapshot the template, so editing it does not change existing shifts; the seeded week is naturally unfillable. | Output reviewed by hand. |

### Decisions made while building (not in the plan)

- **Solver:** at most 500 positions per solve (the search recurses once per placement; above that `ValueError`,
  returned as 422 `validation_error`); the trace is capped at 20 000 events (`trace_truncated`); a preference is
  worth 120 minutes of hours spread; inputs are sorted by id and start time, so list order never changes a result.
- **Availability:** a week is "past" when its Sunday is before this week's Sunday in `Asia/Jerusalem`; answers can
  only be saved for active employees (`user_not_assignable`), which includes a manager answering for someone;
  a PUT must carry at least one answer, each shift at most once, and nothing is saved if one shift is invalid.
- **Authorization before existence:** an employee naming another user gets 403 even for an id that does not exist;
  an employee reading a draft schedule gets `schedule_not_found`, so the draft's existence stays private.
- **Edits:** overlap is reported before minimum rest when both apply; `propose_schedule` is allowed on a published
  week (it saves nothing); a generate for a week with no active employees simply returns every slot unfilled.
- **Explanations:** an employee who did not answer `available` is never blamed on another rule. Found by running
  `debug-schedule` on the seeded week: the report said "Omer excluded by minimum rest" for someone who never
  offered to work the shift. Fixed with failing tests first (commit `fix:` after its `test:`).

### Validation results

| # | Result |
|---|---|
| 1 | `pytest -q`: 670 passed (276 at the end of plan 001). |
| 2 | `pytest tests/unit/scheduler -v`: all 149 pass; the ten matrix cases pass by name (no solution, tight solution, fairness, the five hard constraints in isolation, preferred honored) plus boundaries, DST, determinism, budget, input checks and 60 random instances equal to exhaustive search. |
| 3 | No match for sqlalchemy, fastapi, app.db / repositories / services / models or `datetime.now` in `app/scheduler/`. |
| 4 | `ruff check` and `ruff format --check` clean. Routers and schemas pass the layering greps. |
| 5 | `alembic check`: no new upgrade operations; only migration `0001` exists. |
| 6 | 13 of 13 protected operations return 401 without a token; all 9 manager-only operations (3 templates, generate shifts, generate, publish, add, replace, remove) return 403 for an employee; cross-user availability read and write return 403; an employee reading a draft gets 404. |
| 7 | Seed twice on the dev database: first run created 60 availabilities, 1 schedule, 21 assignments; second run created 0 rows. A test proves the seeded schedule breaks no hard constraint with plain arithmetic. |
| 8 | HTTP smoke test (real server, dev database, seeded manager): generate shifts created 0 (already there); generate schedule returned a 21-of-26 draft with five sentences; adding the next shift gave 409 `min_rest_violation`; an overlapping temporary shift gave 409 `shift_overlap`; adding someone against their availability gave 201 with `availability_ignored` and `shift_overstaffed`; publish gave `published`; a second publish gave 409 `schedule_published`; generate after publish gave 409. Smoke rows were deleted afterwards. |
| 9 | Employee: 404 before any schedule and for a draft; 200 once published; `PUT /api/availabilities` after the schedule exists gave 409 `availability_locked`. |
| 10 | Solver speed: the seed-shaped week, a dense 7-day 12-employee week and three harder weeks (63 positions) each solved in under 10 ms (222 to 481 steps). |
| 11 | `explain()` returns exactly "Tuesday 07:00 needs 3, only 2 available; Dana excluded by minimum rest" (unit test). |
| 12 | `debug_schedule.py --week 2026-11-15` named every unfilled shift, who was excluded and by which shift, who did not answer, and the what-if numbers (no rest rule: 25 of 26); a non-Sunday and a week without shifts exit 1 with the domain message; nothing was written. The `/debug-schedule` skill itself could not be invoked in this session (see Deferred). |
| 13 | History reads docs → plan → tests → code: each step is a `test:` commit followed by its `feat:`, with `docs:` and `chore:` where planned. Every `ErrorCode` value appears in the error-handling table (checked by script). |

### Deferred

- **Live `/debug-schedule` check.** Skills load at session start, so the new skill can only be invoked in the next
  session. Verified instead: the script, its report tests, and the skill file against the template of
  `add-pay-rule`. Confirm once: run `/debug-schedule 2026-11-15` after the next `/clear`.
- **Concurrent availability saves.** Two simultaneous `PUT`s by the same person for the same new shift could hit the
  unique constraint and return a 500; shift generation, schedule creation and assignment edits already map that
  race to a domain error. Unlikely for one person's form; fix with the same savepoint pattern if it ever shows.
- **Rest across the week boundary** (Saturday night to Sunday morning) is not checked; documented in the glossary.
- **Assistant tool, extra constraints** ("Dana can't work Tuesday") and a cross-week "my assignments" endpoint
  belong to plans 004 and 003 respectively.
