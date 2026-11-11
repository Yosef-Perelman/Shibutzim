# AGENTS.md

Instructions for any AI coding agent working in this repository. This file is the **index**: it says what to read
for which task. Load docs on demand and keep context small.

## Reply canary

**Start every chat reply to the user with `Yosef my king:`** – only in chat replies, never in code, docs, commits
or files. If a reply ever lacks it, the user knows these instructions were lost (for example after a context reset)
and will reload them.

## Project in five lines

- **Shibutzim** (Hebrew for "assignments"): shift scheduling and pay for small teams of hourly workers.
- Managers define shifts, generate a weekly schedule with a constraint solver, edit and publish it; employees submit
  availability, clock in and out, and see their hours and pay.
- An AI assistant answers questions about shifts, pay and policy by calling tools over the same services as the UI,
  with handbook retrieval and human-confirmed write proposals.
- Server: Python 3.12, FastAPI, PostgreSQL + pgvector. Client: React + TypeScript + MobX + Mantine.
- `pay/` and `scheduler/` are pure, exhaustively tested modules; authorization lives in services.

## Start of every session

1. Read [plans/ROADMAP.md](plans/ROADMAP.md) and find the plan that is `in progress`.
2. Read that plan file, including its status, amendments and open questions.
3. Load only the docs and rules the current task needs (map below).
4. If the current plan is `draft`, do not write code: wait for the user's approval.

## Plan-to-plan workflow

No implementation before a written plan the user approved ([planning-rules.md](docs/rules/planning-rules.md)).

> When a plan's validation passes: set its status to `done` (with a short "what changed vs. plan" note), update
> `plans/ROADMAP.md`, commit on the plan branch, **merge the branch into `main` locally with a merge commit**
> (`git switch main && git merge --no-ff plan/NNN-short-name`), then use `/new-plan` to draft the next plan from
> the roadmap and **stop and wait for the user's approval** before writing any code.

After a plan is closed the user may run `/clear`; `CLAUDE.md → AGENTS.md → ROADMAP.md → current plan` must be
enough to continue exactly where work stopped. Project state lives in files, not in the chat.

## Task → what to read

| Task | Read |
|---|---|
| Understand the product or a business rule | [docs/product-definition.md](docs/product-definition.md) |
| Any server code | [docs/architecture.md](docs/architecture.md) §3–§7, [coding-rules](docs/rules/coding-rules.md), [naming-rules](docs/rules/naming-rules.md) |
| New or changed endpoint | + [error-handling-rules](docs/rules/error-handling-rules.md), [testing-rules](docs/rules/testing-rules.md); follow `/new-endpoint` |
| Models, migrations, queries, seed | + [database-rules](docs/rules/database-rules.md), architecture §5 |
| Pay calculation or pay rules | product-definition §5.4 and §6.1, [testing-rules](docs/rules/testing-rules.md) (pay matrices) |
| Scheduler / solver | product-definition §5.2 and §6.2, architecture §6.2, testing-rules (scheduler matrix) |
| Assistant, tools, prompts, RAG, evals | product-definition §5.5 and §7, architecture §6.4–§6.6 |
| Client code | architecture §9, [design-system](docs/design-system.md), [ui-rules](docs/rules/ui-rules.md), [naming-rules](docs/rules/naming-rules.md), [style-rules](docs/rules/style-rules.md) |
| Domain words, names in code / DB / API | [docs/glossary.md](docs/glossary.md) |
| Writing or closing a plan | [planning-rules](docs/rules/planning-rules.md), [plans/ROADMAP.md](plans/ROADMAP.md) |
| Commits, branches | [git-rules](docs/rules/git-rules.md) |

## Guardrails

Enforced by tooling (`.claude/settings.json` and `.claude/hooks/`):

- `.env` files are never read or edited (`.env.example` is allowed). Secrets come from environment variables.
- Committed Alembic migrations are never edited; add a new migration instead. A freshly generated, uncommitted
  migration may still be corrected by hand.
- After every `.py` edit, `ruff format`, `ruff check --fix` and `pytest -q -x` run automatically; failures are fed
  back and must be fixed before moving on.
- `git push --force` and `rm -rf` are denied.
- Every Claude Code session is archived to `conversations/` (raw JSONL + readable Markdown, git-ignored) when it
  ends or is compacted; `python3 .claude/hooks/archive_conversation.py --backfill` archives existing ones.
- The `qa` subagent can write only test and eval files.

Enforced by you:

- Don't add dependencies or features beyond the approved plan without asking.
- Never push to the remote unless the user asks.
- Explain decisions briefly as you go; when there is a real trade-off, show the options and recommend one.
- Small, verifiable steps; tests first for pure logic.
- Use macOS commands (BSD `sed -i ''`, `open`, Homebrew).
- The local planning brief (`docs/archive/SHIBUTZIM_BRIEF.md`) is git-ignored and private. Never commit it, and
  don't rely on it: everything needed is in `docs/` and `plans/`.
- UI reference screenshots in `design/references/` are git-ignored and private (other sites' designs). Plan 003 derived
  `docs/design-system.md` from them; commit only what is derived.

Hooks guard the Edit and Write tools. A shell command can still bypass them, so don't use Bash to write files the
hooks protect.

## Never compromise on

Pay tests · scheduler tests · authorization in services · the docs and plans trail.

## Subagents and skills

| Name | Kind | Use for |
|---|---|---|
| `backend` | subagent | server code only (`server/`) |
| `frontend` | subagent | client code only (`client/`) |
| `qa` | subagent | writing and running tests and evals; read-only on source |
| `/new-plan` | skill | drafting the next plan from the roadmap |
| `/new-endpoint` | skill | adding a REST endpoint: tests first (401/403 matrix), schema, repository, service, router |
| `/add-pay-rule` | skill | adding a pay rule with its five-case matrix; `dry run` lists the work and stops |
| `/debug-schedule` | skill | explaining why the solver couldn't fill a week (runs `scripts/debug_schedule.py`, read-only) |

## Common commands

Server commands run from `server/`, client commands from `client/`; `docker compose` runs from the repository root. Copy `.env.example` to
`.env` only if you need to change a default (the database listens on host port **5433**).

| Purpose | Command |
|---|---|
| Show what's next | `cat plans/ROADMAP.md` |
| Start the database | `docker compose up -d db` (repo root) |
| Install server deps | `uv sync` |
| Run migrations | `uv run alembic upgrade head` |
| Check models match migrations | `uv run alembic check` |
| New migration | `uv run alembic revision --autogenerate --rev-id NNNN -m "short description"` |
| Seed demo data (idempotent) | `uv run python scripts/seed.py` |
| Run the API | `uv run fastapi dev app/main.py` (docs at `/docs`) |
| Tests | `uv run pytest -q` |
| Pay matrix, by name | `uv run pytest tests/unit/pay -v` (without `-q`, which cancels `-v`) |
| Scheduler matrix, by name | `uv run pytest tests/unit/scheduler -v` |
| Lint and format | `uv run ruff check --fix . && uv run ruff format .` |
| Client dev server | `cd client && npm run dev` (API on port 8000; Vite proxies `/api`; see `client/.env.example`) |
| Client checks | `cd client && npm run lint && npm run typecheck && npm test` |
| Client build, format | `cd client && npm run build` · `npm run format` |
| Assistant evals | *(plan 004)* `uv run python -m evals.run` |
