# Plan 001 – Server skeleton, auth, time tracking and pay

| | |
|---|---|
| **Status** | approved |
| **Date** | 2026-11-10 |
| **Related docs** | [product-definition.md](../docs/product-definition.md) §3–§6, [architecture.md](../docs/architecture.md) §3–§8, [glossary.md](../docs/glossary.md), [coding](../docs/rules/coding-rules.md), [database](../docs/rules/database-rules.md), [error-handling](../docs/rules/error-handling-rules.md), [testing](../docs/rules/testing-rules.md) rules |
| **Roadmap** | plan 001 of 005 |
| **Branch** | plan/001-skeleton-auth-pay |

## Amendment on approval

Approved on 2026-11-10 as drafted. All sixteen open questions were approved with their suggested answers. Per open
question 11, plan 002's roadmap row now includes shift-template CRUD and weekly shift generation.

## Goal

A running FastAPI server on a local PostgreSQL + pgvector database, with every table of the data model migrated and
seeded, JWT login with roles enforced in services, clock-in/clock-out and manager-corrected time entries, and a
pure, exhaustively tested pay module exposed through `GET /api/pay`. After this plan an employee can log in, clock
in and out, and see a correct pay breakdown; a manager can do the same for anyone. The `add-pay-rule` skill is
built at the end on top of the finished pay module, and the `new-endpoint` skill is built from the first real
endpoints and used for the rest.

## Scope

### In

1. **Tooling**: uv, Python 3.12 (installed by uv), Docker Desktop; `server/pyproject.toml` with ruff and pytest
   configuration.
2. **Local database**: `docker-compose.yml` with `pgvector/pgvector:pg16`, a named volume, a healthcheck, and an
   init script that also creates the `shibutzim_test` database.
3. **Configuration**: `app/config.py` (pydantic-settings) and `.env.example` documenting every variable.
4. **App skeleton**: `app/main.py` with the error handlers, CORS for the Vite dev server, `GET /api/health`.
5. **Core**: `core/errors.py` (domain errors + error-code catalogue), `core/security.py` (bcrypt, JWT),
   `core/time.py` (work-day and week helpers in `Asia/Jerusalem`).
6. **All models and migration `0001`**: the nine tables of architecture §5, including `CREATE EXTENSION vector`,
   with constraints and indexes per database-rules.
7. **Seed**: `scripts/seed.py`, idempotent – one manager, five employees with different hourly rates, shift
   templates, shifts for the current and next week, some availability, and time entries for the previous and current
   month that include a split shift, a midnight crossing and overtime days.
8. **Auth**: `POST /api/auth/login`, `GET /api/auth/me`; `current_user` dependency; `ensure_manager`,
   `ensure_self_or_manager` in services.
9. **Pay module (TDD)** in `app/pay/`: `PayRules`, `OvertimeTier`, `PayBreakdown`, `DayBreakdown`, `TierLine`, and
   `calculate(entries, hourly_rate, rules, tz)`. Designed so premiums (night, weekend) can be added as further rules.
10. **Time entries**: `POST /api/time-entries/clock-in`, `POST /api/time-entries/clock-out`,
    `GET /api/time-entries` (own, or any user for a manager), and manager-only `POST /api/time-entries`,
    `PATCH /api/time-entries/{id}`, `DELETE /api/time-entries/{id}`.
11. **Pay endpoints**: `GET /api/pay?user_id=&from=&to=` (own, or anyone for a manager) and manager-only
    `GET /api/pay/team?from=&to=`.
12. **Tests**: the pay matrix (unit), time and auth helpers (unit), services and API tests with the authorization
    matrix (401 / 403) for every endpoint above.
13. **Docs**: fill the plan-001 commands in AGENTS.md; update the glossary and error-code catalogue with anything new.
14. **Migration guard fix**: the PreToolUse hook blocks editing a migration only when git already tracks it, so a
    freshly generated, uncommitted migration can be corrected by hand as database-rules require.
15. **`new-endpoint` skill** (`.claude/skills/new-endpoint/`), written after the auth and time-entry endpoints and
    used to build the pay endpoints.
16. **`add-pay-rule` skill** (`.claude/skills/add-pay-rule/`), after the plan's validation passes.
17. **Conversation archive**: a hook that copies every Claude Code session transcript into `conversations/`
    (raw JSONL + readable Markdown, git-ignored) when a session ends or before it is compacted, so the full
    human–AI collaboration can be analyzed later. Claude Code's own copies are deleted after 30 days by default.

### Out

- Users CRUD endpoints (users come from the seed in v1).
- Shift-template, shift, availability and schedule endpoints, and the solver (plan 002 – see open question 11).
- Client (plan 003); assistant, handbook content and ingestion (plan 004); Dockerfile, CI, deployment (plan 005).
- Refresh tokens, logout/revocation, password reset, rate limiting.
- Weekly overtime, night/weekend premiums, unpaid breaks (designed for, not built).
- UI design system (first steps of plan 003).

## Assumptions

- **Verified**: Homebrew 6.0 is installed; `uv`, `ruff` and Docker are **not**; the system `python3` is 3.9.6, so
  Python 3.12 comes from `uv python install 3.12`; Node 24 is installed (not needed until plan 003).
- **Not verified**: Docker Desktop can be installed on this Mac (Apple Silicon or Intel both supported by the
  `pgvector/pgvector:pg16` image).
- Port 5432 is free locally; if not, Compose maps another port and `.env` follows.
- The `post_edit_py.py` hook starts running ruff and pytest as soon as `server/pyproject.toml` exists. Tests that
  need the database fail fast with a clear "start the DB" message when Docker is down.
- The embedding model for plan 004 produces 768-dimensional vectors (see open question 6).

## Steps

Each step is one commit on `plan/001-skeleton-auth-pay`. `test:` commits come before the `feat:` commit they cover.

1. **Branch and tools** – create the branch from `main` and commit the approved plan and roadmap row as its first
   commit (git-rules); `brew install uv`; `uv python install 3.12`. Yosef installs Docker Desktop
   (`brew install --cask docker-desktop`, first launch, `docker run --rm hello-world`).
2. **Conversation archive** (`chore:`) – `.claude/hooks/archive_conversation.py` (Python 3.9, standard library),
   registered in `.claude/settings.json` for `SessionEnd` (exit and `/clear`) and `PreCompact`. From the hook
   input's `transcript_path` it writes `conversations/raw/<date>-<session_id>.jsonl` (exact copy) and
   `conversations/<date>-<session_id>.md` (your messages, Claude's replies, one line per tool call). Re-running
   overwrites the same session's files, so they always hold the whole session. It never blocks Claude Code: errors
   go to stderr with exit code 0. Add `conversations/` to `.gitignore`; backfill today's sessions once by running
   the script on the existing transcripts.
3. **Project scaffold** (`chore:`) – `server/pyproject.toml` (dependencies listed in open question 5, ruff rules from
   style-rules, pytest config), `uv.lock`, `docker-compose.yml` + `docker/initdb/01-test-db.sql`, `.env.example`,
   `app/config.py`, `app/main.py` with `GET /api/health`, empty package folders per architecture §4.
   Check: `docker compose up -d db` healthy; `uv run fastapi dev app/main.py` → `/api/health` returns 200.
4. **Migration guard fix** (`fix:`) – `pre_edit_guard.py` blocks an Edit/Write of a file in
   `server/alembic/versions/` only when `git ls-files --error-unmatch` says git tracks it. Re-run the plan-000
   simulated cases plus two new ones (uncommitted migration → allowed; committed migration → blocked). Update the
   guardrail line in AGENTS.md and database-rules.
5. **Errors and time helpers** – `test:` unit tests for the error shape mapping and `core/time.py` (work day of an
   entry crossing midnight, week start for any day, DST boundary in `Asia/Jerusalem`); then `feat:` implementation
   and exception handlers in `main.py`.
6. **Pay tests** (`test:`) – the full matrix from testing-rules, written before any pay code, with expected values
   computed by hand in the test comments: exactly 8h; 9h; 12h; split shift 07–11 + 16–22; 22:00–06:00 crossing
   midnight; two work days in one period; no entries; rounding to the cent. Plus: entries given out of order; an
   entry exactly at a tier boundary in minutes (8h00m vs 8h01m); custom tiers in `PayRules`.
7. **Pay module** (`feat:`) – implement until step 6 passes. Durations in integer seconds; amounts in `Decimal`;
   group by work day; walk the tiers; round per tier line (open question 7).
8. **Models and migration 0001** (`feat:`) – all nine models; `alembic init`, env wired to settings and models;
   autogenerate `0001_initial_schema`, review and correct it by hand (allowed by step 4), add
   `CREATE EXTENSION vector`. Check: `upgrade head` → `downgrade base` → `upgrade head` all succeed.
9. **Test infrastructure** (`test:`) – `conftest.py`: migrate `shibutzim_test` once per session, transaction +
   savepoint rollback per test, factories for users and time entries, an authenticated API client per role.
10. **Auth** – `test:` login success / wrong password / inactive user, `me`, 401 without or with an expired token;
   then `feat:` `core/security.py`, user repository, auth service, routers, `current_user` dependency and the two
   authorization helpers.
11. **Time entries** – `test:` service and API tests: clock in/out, double clock-in → 409 `already_clocked_in`,
    clock-out without open entry → 409 `not_clocked_in`, manual entry validation (`clock_out_before_clock_in`,
    `entry_too_long`, `time_entry_overlap`), employee cannot create/patch/delete or list others → 403; then `feat:`.
12. **`new-endpoint` skill** (`chore:`) – `.claude/skills/new-endpoint/SKILL.md`, codifying the pattern that steps
    10–11 established: schema → repository → service with authorization → router → tests (401/403 matrix, error
    codes, happy path) → glossary and error-code catalogue. Built now because two real endpoint groups exist to copy
    from; written earlier, it would guess the pattern.
13. **Pay endpoints** – built **by following `/new-endpoint`**: `test:` own pay, manager reads anyone, employee reads
    other → 403, team pay manager-only, open entries excluded, range by work day inclusive; then `feat:` pay service
    + routers. Any gap found in the skill is fixed in the same step and noted in "What changed vs. plan".
14. **Seed** (`feat:`) – `scripts/seed.py`, idempotent (re-running changes nothing). Demo password from
    `SEED_PASSWORD`, documented in `.env.example`.
15. **Docs** (`docs:`) – AGENTS.md commands for plan 001, glossary and error-code catalogue updates.
16. **Validation** – run every item below; fix and re-run until green.
17. **`add-pay-rule` skill** (`chore:`) – `SKILL.md` plus a matrix checker script (open question 13); validated by a
    dry run for a hypothetical "night premium" that lists the files and test cases it would create and stops.
18. **Close** – fill "What changed vs. plan", set `done`, update ROADMAP, commit `plan: close plan 001` on the
    branch, then `git switch main && git merge --no-ff plan/001-skeleton-auth-pay`, delete the branch, draft plan
    002 with `/new-plan`, stop.

## Validation

- `docker compose up -d db` reports healthy; `uv run alembic upgrade head`, `downgrade base`, `upgrade head`
  succeed on an empty database.
- `uv run ruff check .` and `uv run ruff format --check .` are clean.
- `uv run pytest -q` passes; `uv run pytest -q tests/unit/pay -v` shows every pay-matrix case by name.
- Every endpoint in scope has a 401 test and, where a role or ownership rule applies, a 403 test.
- Running `uv run python scripts/seed.py` twice leaves row counts unchanged.
- Manual smoke test with `curl` against `fastapi dev`:
  1. log in as a seeded employee → token;
  2. clock in, clock out → entry listed;
  3. `GET /api/pay` for the current month → breakdown whose per-day tiers match a hand calculation for one seeded
     overtime day;
  4. same employee requests another user's pay → 403 with `{ "error": { "code": "forbidden", ... } }`;
  5. no token → 401 with the same shape;
  6. log in as the manager → `GET /api/pay/team` returns every employee.
- The pure-module rule holds: `grep -rE "sqlalchemy|fastapi|app\.(db|repositories|services)" server/app/pay`
  returns nothing.
- Conversation archive: after `/clear` in a live session, `conversations/` holds that session's `.jsonl` (byte-identical
  to Claude Code's transcript) and a readable `.md`; `git check-ignore conversations/x.md` confirms it is ignored;
  today's sessions are backfilled.
- Migration guard: simulated hook input shows an uncommitted migration is editable and a committed one is blocked.
- The pay endpoints were built through `/new-endpoint`, and the resulting files match the skill's checklist.
- The `add-pay-rule` dry run lists the five matrix cases and the files to touch, and changes nothing.
- After the merge, `git log --first-parent main` shows the plan-001 merge commit and `git log main` shows every
  step commit.

## Rollback

- Code: abandon or revert the branch; `main` is untouched until the merge.
- Database: `uv run alembic downgrade base`, or `docker compose down -v` to delete the local volume.
- Tools: `brew uninstall uv`; Docker Desktop can stay or be removed from Applications.

## Open questions (each with a suggested answer)

1. **Confirm the product decisions carried over from the planning brief**: Gemini behind an interface; TypeScript
   client; daily-only overtime in v1; both clock-in/out and manager manual entry; no night/weekend premiums in v1
   (but `PayRules` ready for them); public repository; minimum rest 8 hours, configurable.
   → *Suggested:* confirm all seven; they are already written into product-definition.md.
2. **Who installs system tools?**
   → *Suggested:* I run `brew install uv` and `uv python install 3.12`; you install Docker Desktop yourself
   (`brew install --cask docker`), because it asks for your password and needs a first GUI launch.
3. **Sync or async SQLAlchemy?**
   → *Suggested:* **sync** SQLAlchemy 2 with FastAPI's threadpool. Simpler code and tests, no async pitfalls in
   repositories, and far more than enough throughput for this app. Async is a contained change later if needed.
4. **Postgres driver?**
   → *Suggested:* `psycopg` 3 (binary), the maintained successor of psycopg2, supported by SQLAlchemy 2.
5. **Dependencies.** Runtime: `fastapi[standard]`, `pydantic-settings`, `sqlalchemy`, `psycopg[binary]`, `alembic`,
   `pgvector`, `pyjwt`, `bcrypt`, `tzdata`. Dev: `pytest`, `ruff`.
   → *Suggested:* approve this list. PyJWT and bcrypt directly instead of `python-jose` / `passlib`, which are poorly
   maintained. `tzdata` so `Asia/Jerusalem` works in slim containers (plan 005). `httpx` comes with
   `fastapi[standard]` for the test client.
6. **Embedding dimension for `handbook_chunks.embedding`** (needed now because the column is in migration 0001).
   → *Suggested:* `vector(768)` – Gemini embeddings can be requested at 768 dimensions, which is plenty for ~10
   handbook sections. Changing it later is one new migration plus re-ingestion.
7. **Pay rounding.** Round each tier line to the cent and sum the lines, or sum unrounded and round the total?
   → *Suggested:* round each **tier line** (`ROUND_HALF_UP`) and make every total the sum of its lines, so the
   breakdown always adds up exactly, like a payslip. Hours are never rounded.
8. **Pay range semantics.**
   → *Suggested:* `from` and `to` are **work-day dates, inclusive**; an entry belongs to the range if its work day
   does. Open entries (no clock-out) are excluded and reported as a count in the response.
9. **Overlapping time entries for one employee.**
   → *Suggested:* reject with 409 `time_entry_overlap`. Overlaps would double-count pay and are always a data error.
10. **Team pay endpoint now?** `GET /api/pay/team` is not named in the roadmap.
    → *Suggested:* yes. Product-definition says a manager sees everyone's pay, and the plan-004 tool
    `get_team_hours` needs a service for it.
11. **Shift-template and shift endpoints are not assigned to any roadmap plan.** The manager must define templates
    and required staff before scheduling.
    → *Suggested:* add "shift-template CRUD and weekly shift generation" to plan 002's roadmap row on approval of
    this plan. The tables exist from migration 0001.
12. **JWT lifetime.**
    → *Suggested:* 8 hours, HS256, secret from `JWT_SECRET`; no refresh token in v1 (a work shift fits in one
    token; re-login is acceptable for a demo).
13. **How does `add-pay-rule` "fail if a matrix case is missing"?**
    → *Suggested:* every rule's tests use one parametrized test with case ids `at_boundary`, `crossing_midnight`,
    `split_shift`, `with_overtime_tiers`, `zero_hours`, marked `@pytest.mark.pay_rule("<rule_name>")`. A checker
    script in the skill folder runs `pytest --collect-only -m pay_rule -q` and fails if a rule lacks any case id.
    Deterministic and independent of the agent's diligence.
14. **Demo passwords.**
    → *Suggested:* one demo password for all seeded users, read from `SEED_PASSWORD` (default documented in
    `.env.example`), so no credential is hard-coded in source.
15. **Running the full suite after every edit needs the database.**
    → *Suggested:* keep it (plan 000 decision); `conftest.py` checks the connection first and fails with
    "Database not reachable – run `docker compose up -d db`" instead of a stack trace.

16. **What goes into the readable Markdown of an archived conversation?**
    → *Suggested:* your messages and Claude's replies in full, each tool call as one line (tool + its description),
    no tool output and no internal reasoning. The raw JSONL keeps everything for deeper analysis, so the Markdown
    can stay short enough to actually read.

## What changed vs. plan

*(filled in when the plan is closed)*
