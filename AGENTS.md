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

> When a plan's validation passes: set its status to `done` (with a short "what changed vs. plan" note and the
> `--audit` numbers), update
> `plans/ROADMAP.md`, commit on the plan branch, **merge the branch into `main` locally with a merge commit**
> (`git switch main && git merge --no-ff plan/NNN-short-name`), then use `/new-plan` to draft the next plan from
> the roadmap and **stop and wait for the user's approval** before writing any code.

After a plan is closed the user may run `/clear`; `CLAUDE.md → AGENTS.md → ROADMAP.md → current plan` must be
enough to continue exactly where work stopped. Project state lives in files, not in the chat.

## Task → what to read

| Task | Read |
|---|---|
| Understand the product or a business rule | [docs/product-definition.md](docs/product-definition.md) |
| Deploy, CI, Cloud Run, Supabase, secrets, rollback | [docs/deployment.md](docs/deployment.md), architecture §10 |
| Any server code | [docs/architecture.md](docs/architecture.md) §3–§7, [coding-rules](docs/rules/coding-rules.md), [naming-rules](docs/rules/naming-rules.md) |
| New or changed endpoint | + [error-handling-rules](docs/rules/error-handling-rules.md), [testing-rules](docs/rules/testing-rules.md); follow `/new-endpoint` |
| Models, migrations, queries, seed | + [database-rules](docs/rules/database-rules.md), architecture §5 |
| Pay calculation or pay rules | product-definition §5.4 and §6.1, [testing-rules](docs/rules/testing-rules.md) (pay matrices) |
| Scheduler / solver | product-definition §5.2 and §6.2, architecture §6.2, testing-rules (scheduler matrix) |
| Assistant, tools, prompts, RAG, evals | product-definition §5.5 and §7, architecture §6.4–§6.6 |
| Client code | architecture §9, [design-system](design/design-system.md), [ui-rules](docs/rules/ui-rules.md), [naming-rules](docs/rules/naming-rules.md), [style-rules](docs/rules/style-rules.md) |
| Domain words, names in code / DB / API | [docs/glossary.md](docs/glossary.md) |
| Writing or closing a plan | [planning-rules](docs/rules/planning-rules.md), [plans/ROADMAP.md](plans/ROADMAP.md) |
| Commits, branches | [git-rules](docs/rules/git-rules.md) |

## Guardrails

Enforced by tooling (`.claude/settings.json` and `.claude/hooks/`):

- `.env` files are never read or edited (`.env.example` is allowed). Secrets come from environment variables.
- Committed Alembic migrations are never edited; add a new migration instead. A freshly generated, uncommitted
  migration may still be corrected by hand.
- After every `.py` edit, `ruff format`, `ruff check --fix` and `pytest -q -x` run automatically; failures are fed
  back and must be fixed before moving on. The same checks (and Prettier and ESLint for `client/` TypeScript) run
  after a Bash command that changed source files, so a shell write is checked too.
- **Who may write where** is one table in `.claude/hooks/scope_guard.py`, applied to Edit/Write and to Bash writes
  (redirects, heredocs, `tee`, `sed -i`, `mv`, inline `python3 -c` scripts): the main session may not write under
  `server/` or `client/src/`; `backend` writes `server/` and `docs/`, `frontend` writes `client/` and `docs/`, `qa`
  writes only tests and evals. A blocked call says which agent to use.
- A committed git pre-commit hook (`.githooks/pre-commit`) runs ruff and pytest when `server/` is staged, and lint,
  typecheck, Prettier and the client tests when `client/` is staged, and the hook tests when `.claude/hooks/` is
  staged. A deletion counts as a change. It needs `git config core.hooksPath .githooks`
  once per clone; a session-start check warns when that is missing. Skipping it with `--no-verify` or `-n` is denied.
- `git push --force` and `rm -rf` are denied.
- Every Claude Code session is archived to `conversations/` (raw JSONL, subagent transcripts and readable Markdown
  with a "Subagents invoked" list, git-ignored) when it ends or is compacted;
  `python3 .claude/hooks/archive_conversation.py --backfill` archives existing ones and `--audit` prints, per
  session, the Agent calls by type and the Bash commands that wrote source through the shell.

Enforced by you:

- **Delegate source work.** The main session plans, delegates, reviews and edits docs, plans, `.claude/`, README
  and CI. Source under `server/` is changed by the `backend` subagent, under `client/src/` by `frontend`, tests by
  `qa`, each as the owner the plan names for that step; the scope guard blocks the main session otherwise. Never
  create `.claude/main-edits.allow` (the human's escape hatch that turns the block into a log entry).
- Don't add dependencies or features beyond the approved plan without asking.
- Never push to the remote unless the user asks.
- Explain decisions briefly as you go; when there is a real trade-off, show the options and recommend one.
- Small, verifiable steps; tests first for pure logic.
- Use macOS commands (BSD `sed -i ''`, `open`, Homebrew).
- The local planning brief (`docs/archive/SHIBUTZIM_BRIEF.md`) is git-ignored and private. Never commit it, and
  don't rely on it: everything needed is in `docs/` and `plans/`.
- UI reference screenshots in `design/references/` are git-ignored and private (other sites' designs). Plan 003 derived
  `design/design-system.md` from them; commit only what is derived.

The `.env` and migration guards cover the file tools only, so don't use Bash to write files they protect. The scope
guard also parses Bash, but only on a best-effort basis (it can miss a write and can over-block); the pre-commit
hook and CI are the backstop.

## Never compromise on

Pay tests · scheduler tests · authorization in services · the docs and plans trail.

## Subagents and skills

| Name | Kind | Model | Use for |
|---|---|---|---|
| `backend` | subagent | `claude-sonnet-5-5` | server code only (`server/`) |
| `frontend` | subagent | `claude-sonnet-5-5` | client code only (`client/`) |
| `qa` | subagent | `claude-sonnet-5-5` | writing and running tests and evals; read-only on source |
| `/new-plan` | skill | – | drafting the next plan from the roadmap |
| `/new-endpoint` | skill | – | adding a REST endpoint: tests first (401/403 matrix), schema, repository, service, router |
| `/add-pay-rule` | skill | – | adding a pay rule with its five-case matrix; `dry run` lists the work and stops |
| `/debug-schedule` | skill | – | explaining why the solver couldn't fill a week (runs `scripts/debug_schedule.py`, read-only) |

## Common commands

Server commands run from `server/`, client commands from `client/`; `docker compose` runs from the repository root. Copy `.env.example` to
`.env` only if you need to change a default (the database listens on host port **5433**).

| Purpose | Command |
|---|---|
| Show what's next | `cat plans/ROADMAP.md` |
| Enable the pre-commit hook (once per clone, repo root) | `git config core.hooksPath .githooks` |
| Hook tests (stdlib `unittest`, repo root) | `python3 -m unittest discover -s .claude/hooks/tests` |
| Delegation audit of archived sessions | `python3 .claude/hooks/archive_conversation.py --audit` |
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
| Production image locally | `docker compose --profile app up -d --build` (repo root; app at http://localhost:8080, same database) |
| MCP server (stdio; needs `SHIBUTZIM_MCP_TOKEN`) | `cd server && uv run python -m app.mcp` |
| Regenerate the PWA icons from `client/public/icon.svg` | `cd client && npm run icons` |
| Release | merge to `main`, then `git push origin main`; CI deploys (see [docs/deployment.md](docs/deployment.md)) |
| Client checks | `cd client && npm run lint && npm run typecheck && npm test` |
| Client build, format | `cd client && npm run build` · `npm run format` |
| Ingest the handbook (needs `GEMINI_API_KEY`) | `uv run python scripts/ingest_handbook.py` |
| Assistant evals (real model, uses the provider's quota) | `uv run python -m evals.run --list`, then `--only <ids>`; no `--only` runs all fifteen |
