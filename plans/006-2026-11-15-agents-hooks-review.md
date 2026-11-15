# Plan 006 – Agents, hooks and review

| | |
|---|---|
| **Status** | in progress |
| **Date** | 2026-11-15 |
| **Related docs** | [AGENTS.md](../AGENTS.md), [planning-rules](../docs/rules/planning-rules.md), [git-rules](../docs/rules/git-rules.md), [testing-rules](../docs/rules/testing-rules.md), [README](../README.md) §"How this was built with AI" |
| **Roadmap** | plan 006 of 007 |
| **Branch** | plan/006-agents-hooks-review |

## Goal

Every source change in this repository is made by the right subagent, checked by hooks whatever tool wrote the
file, and reviewed before it reaches `main`. After this plan: a shell write into `server/` or `client/src` is
blocked for every agent; ruff and the tests run after Bash commands that changed files; a committed git
pre-commit hook rejects a commit that fails lint or tests regardless of how the files were written; each agent
has a defined model; a read-only `reviewer` agent checks every plan branch before it is merged; and the plan
template names an owner for every step, so delegation is visible in the plan, enforced by a hook, and auditable
from the session transcripts.

Why now: the archived sessions of plans 000–005 (`conversations/raw`, six sessions) contain **zero** `Agent`
tool calls, and 309 Bash commands wrote files under `server/` or `client/` through the shell (heredocs,
`cat >`, `python3 - <<EOF`, `sed -i`), which the Edit/Write hooks never saw:

| Session | `Agent` calls | Bash calls | Edit/Write calls | Bash commands that wrote source via shell |
|---|---|---|---|---|
| 2026-11-10 5875b1be | 0 | 269 | 9 | 65 |
| 2026-11-10 e2ef46c5 | 0 | 67 | 2 | 20 |
| 2026-11-11 855d1f2f | 0 | 201 | 10 | 57 |
| 2026-11-11 871597cc | 0 | 146 | 0 | 51 |
| 2026-11-11 f530bcf0 | 0 | 248 | 4 | 55 |
| 2026-11-12 57060ed8 | 0 | 282 | 88 | 61 |

The documentation alone (AGENTS.md, the agent files, README §5) did not change behavior; only a hook acts at
the moment of the action.

## Scope

### In

1. **Bash-aware guard** (`PreToolUse`, matcher `Bash`, plus the existing file tools): one `scope_guard.py`
   that blocks shell writes into `server/` and `client/src/` (redirects `>`/`>>`, `tee`, `cat >` and heredocs,
   `python3 -`/`-c` and `perl -i` inline scripts, `sed -i`, `mv`/`cp`/`rsync`/`install`/`truncate`/`dd of=`)
   with the message "use Edit/Write", and applies the per-agent scope from one table: `qa` → tests and evals
   only (replaces `qa_scope_guard.py`, which covered only Edit/Write), `backend` → `server/`, `frontend` →
   `client/`, `reviewer` → no writes, main session and any other agent → no writes under `server/` or
   `client/src/` (docs, plans, `.claude/`, `README.md`, `.github/`, `client/` config files stay editable).
   Allowlist: `git …`, `uv run ruff …`/`ruff …`, `uv run alembic revision …`, `prettier --write`,
   `eslint --fix`, `npm run format|icons`.
2. **Post-Bash checks** (`PostToolUse`, matcher `Bash`): `post_bash_check.py` lists dirty files with
   `git status --porcelain`, compares their mtimes with `.claude/.hook-state.json` (git-ignored), and for files
   that changed since the last check runs ruff format/check on changed `server/**/*.py` plus `pytest -q -x`
   (whole suite: 9 s, deterministic), and prettier/eslint on changed `client/**/*.ts(x)`. Failures come back
   with exit 2. Shared code moves from `post_edit_py.py`/`post_edit_ts.py` into `.claude/hooks/checks.py`, and
   the Edit hooks record the files they checked in the same state file so a file is not checked twice.
3. **Post-edit hook timeout**: keep 60 s (measured: 1,076 tests in 8.9 s with the database up); replace the
   stale message ("see plan 000, open question 1") with what to do; when pytest fails because the database is
   unreachable (the conftest's `DB_UNREACHABLE` text), report one line ("start it with
   `docker compose up -d db`") instead of the pytest tail.
4. **Committed pre-commit hook** `.githooks/pre-commit` (bash; enabled per clone with
   `git config core.hooksPath .githooks`): when staged paths include `server/` → `uv run ruff check .`,
   `uv run ruff format --check .`, `uv run pytest -q`; when they include `client/` → `npm run lint`,
   `npm run typecheck`, `npx prettier --check <staged client files>`, `npm test` (4.7 s). Docs-only commits run
   nothing. `git commit --no-verify`/`-n` is denied in `settings.json`. A `SessionStart` hook
   (`check_setup.py`) warns, as `additionalContext`, when `core.hooksPath` is not `.githooks`, when `uv` is
   missing, or when `client/node_modules/.bin` is missing.
5. **Subagent use made real**: (a) AGENTS.md rule: the main session plans, delegates, reviews and edits docs,
   plans and `.claude/`; source changes under `server/` and `client/src` are made by `backend`/`frontend`,
   tests by `qa`; (b) the scope guard enforces it (item 1); (c) the plan template names an owner per step
   (item 8); (d) the closing checklist includes a subagent audit; (e) `archive_conversation.py` also copies
   `subagents/*.jsonl` + `.meta.json` into `conversations/raw/<date>-<session>/subagents/`, renders a
   "Subagents invoked" list in the Markdown, and gains `--audit [transcript…]` that prints per session: `Agent`
   calls by `subagent_type`, and Bash commands that wrote source via shell. The table above is its first output.
6. **`model:` per agent**: `claude-sonnet-5-5` for `backend`, `frontend`, `qa`; `claude-opus-5-5` for
   `reviewer` (open question 2).
7. **`.claude/agents/reviewer.md`**: read-only (tools `Read, Grep, Glob, Bash`; a frontmatter `PreToolUse`
   Bash hook `reviewer_bash_guard.py` allows only `git diff|log|show|status|ls-files|blame|rev-parse|merge-base`;
   the scope guard denies every write). It reads the plan, `git diff main...HEAD`, and the docs/rules; it checks
   explicitly: pay tests, scheduler tests, authorization in services, the docs and plans trail (glossary,
   product-definition, architecture updated with any rule change; plan steps ↔ commits), layer violations
   (routers with business rules, services without an authorization check, repositories with logic, client
   computing pay or enforcing scheduling rules), missing tests (new endpoint without the 401/403 matrix, pay or
   scheduler change without its matrix), glossary names. It reports findings as `blocker` / `should` / `nit`
   with `file:line` and a verdict; it never edits. It runs as the last step of every plan, before
   `plan: close plan NNN`, and again after blockers are fixed.
8. **`new-plan` skill and template**: every step is `N. **owner** – text` with owner ∈ `backend`, `frontend`,
   `qa`, `reviewer`, `main`; tests-first ordering stays (a `qa` step precedes the `backend`/`frontend` step it
   tests); the last two steps are always `reviewer` – review the branch, and `main` – close. A new template
   section **Review** holds the reviewer's findings and what was done about them. `planning-rules.md` ("Writing a
   good plan", "Closing a plan") and `SKILL.md` steps 4 and 6 are updated; the closing checklist adds: review
   recorded, `--audit` run and its numbers noted in "What changed vs. plan".
9. Docs: AGENTS.md (guardrails, subagents table with models, common commands, the delegation rule), README
   "How this was built with AI" §4–5 and "Run it locally" (`core.hooksPath`), `git-rules.md` (pre-commit hook,
   `--no-verify` never), `.gitignore` (`.claude/.hook-state.json`).

### Out

- Any product change (items 5–8 of the request are plan 007).
- Blocking `git commit`/`git push` from agents, CI changes, branch protection on GitHub.
- A hook that forces the main session to *call* a subagent (not expressible as a hook; the scope guard makes
  not delegating impossible for source files, which is the enforceable half).
- Parsing arbitrary shell perfectly: the guard is regex-based and may over-block (the message says what to use
  instead); the pre-commit hook and CI are the backstop for anything it misses.
- Moving hooks to a plugin, `SubagentStop` quality gates, Claude Code version pinning.

## Assumptions

- Verified against the Claude Code docs on 2026-11-15 (`code.claude.com/docs/en/sub-agents`, `/hooks`):
  - Subagent frontmatter: `name`, `description` required; `model` accepts `sonnet`, `opus`, `haiku`, `fable`, a
    full model ID such as `claude-opus-5-5`, or `inherit`; also `tools`, `disallowedTools`, `permissionMode`,
    `maxTurns`, `skills`, `hooks`. Unknown fields are ignored silently.
  - `.claude/agents/*.md` are scanned automatically; edits are picked up within seconds (a restart is needed
    only when the first file of a new `agents/` directory is created). Invocation: automatic delegation from
    `description`, an explicit request ("use the backend subagent to…"), or `@"backend (agent)"`, which forces
    that agent. `/agents` now prints a reminder to edit the files; the wizard existed up to v2.1.197.
  - `tools: Bash` allows all of Bash; a `disallowedTools: Bash(git push *)` entry removes Bash entirely. The
    documented way to limit Bash inside an agent is a `PreToolUse` hook with `matcher: "Bash"` in its
    frontmatter.
  - `PreToolUse` input has `tool_name`, `tool_input.command` (Bash), `cwd`, `session_id`, `transcript_path`
    and, when the call is made inside a subagent, `agent_id` and `agent_type` (the agent's `name`). Exit code
    2 + stderr blocks the call and shows the reason to the agent. `PostToolUse` for Bash receives
    `tool_response.stdout/stderr/interrupted`; exit 2 feeds stderr back (the command already ran).
    `SubagentStart`/`SubagentStop` fire per spawn with `agent_type`; `SubagentStop` adds
    `agent_transcript_path`. Default command-hook timeout is 600 s; `timeout` is in seconds.
  - Subagent transcripts live in `~/.claude/projects/<project>/<session_id>/subagents/agent-<id>.jsonl` plus
    `agent-<id>.meta.json` (`agentType`, `description`, `pickedEffortModel`, `finished`); seen on disk for the
    drafting session. The main transcript holds the `tool_use` block `name: "Agent"` with `subagent_type`.
    `archive_conversation.py` copies only the main transcript today.
- Verified: the workspace is trusted, so frontmatter hooks in project agents run.
- Verified (measured): `uv run pytest -q` → 1,076 passed in 8.94 s (wall 9.6 s); `npx vitest run` 4.7 s;
  `tsc --noEmit` 1.5 s.
- Not verified: that a `permissions.deny` rule for `git commit --no-verify` matches both `--no-verify` and `-n`
  placements; the validation checks it.
- Assumed: the system `python3` (3.9+) stays the interpreter for hooks, standard library only, as today.
- Assumed: `claude-sonnet-5-5` and `claude-opus-5-5` are valid full IDs for this account (they are the IDs the
  drafting session reports); if a subagent fails to start, fall back to the aliases `sonnet` / `opus`.

## Steps

1. **main** – `test:` hook tests first: `.claude/hooks/tests/test_scope_guard.py`,
   `test_post_bash_check.py`, `test_archive_audit.py` (stdlib `unittest`, run with
   `python3 -m unittest discover -s .claude/hooks/tests`): each test feeds a hook-event JSON on stdin and asserts
   exit code and message. Cases: `cat > server/app/x.py <<'EOF'` blocked for main; same with `agent_type: backend`
   allowed; `python3 - <<EOF` mentioning `client/src/App.tsx` blocked; `uv run ruff format .` allowed;
   `git restore server/app/x.py` allowed; `qa` writing `server/app/x.py` via Edit and via `tee` blocked,
   `server/tests/x.py` allowed; `reviewer` blocked on Edit and on `echo >> docs/x.md`; `frontend` blocked on
   `server/`; main allowed on `plans/`, `docs/`, `.claude/`; `--audit` on a fixture transcript counts 1 Agent
   call of type `qa` and 2 shell writes.
2. **main** – `chore:` `scope_guard.py` (rules table, Bash write detection, allowlist) and the `settings.json`
   `PreToolUse` entries (`Read|Edit|Write|MultiEdit|NotebookEdit` keep `pre_edit_guard.py`; add `scope_guard.py`
   for `Edit|Write|MultiEdit|NotebookEdit|Bash`); remove the `qa` frontmatter hook and delete `qa_scope_guard.py`;
   `.gitignore` entry. Tests of step 1 pass.
3. **main** – `chore:` `checks.py` (shared ruff/pytest/prettier/eslint runners, state file, DB-unreachable
   detection), `post_bash_check.py`, the `PostToolUse` `Bash` entry (timeout 120), and the message fix in
   `post_edit_py.py`; `post_edit_py.py`/`post_edit_ts.py` call `checks.py`.
4. **main** – `chore:` `.githooks/pre-commit` (executable), `check_setup.py` + `SessionStart` entry,
   `permissions.deny` for `git commit --no-verify` / `-n`; `git config core.hooksPath .githooks` run once here.
5. **main** – `chore:` `archive_conversation.py`: subagent transcripts, "Subagents invoked" rendering, `--audit`;
   backfill run (`--backfill`), numbers checked against the table in Goal.
6. **main** – `chore:` `model:` in `backend.md`, `frontend.md`, `qa.md`; `qa.md` scope text updated (shell writes
   are blocked too).
7. **main** – `chore:` `.claude/agents/reviewer.md` + `reviewer_bash_guard.py` (+ its unittest cases: `git diff`
   allowed, `git push`, `ls`, `uv run pytest` blocked).
8. **main** – `docs:` planning template and rules (owner per step, Review section, closing checklist),
   `new-plan/SKILL.md`, AGENTS.md (delegation rule, guardrails, subagents table, commands), README §"How this was
   built" 4–5 and "Run it locally", `git-rules.md`.
9. **reviewer** – review `plan/006-agents-hooks-review` against this plan and the docs; findings recorded under
   **Review** below; blockers fixed by **main** (this plan's files are tooling and docs, which the main session
   owns).
10. **main** – run Validation, fill "What changed vs. plan", close and merge (planning-rules "Closing a plan").

## Validation

- `python3 -m unittest discover -s .claude/hooks/tests` → all pass.
- Live, in the session: `Bash: cat > server/app/x.py <<'EOF'` → blocked with the "use Edit/Write" message and
  no file created; `Bash: cd server && uv run ruff format .` → runs. `Edit server/app/main.py` (a harmless
  comment) from the main session → blocked, message names `backend`.
- Live, subagent: "use the qa subagent to append a line to `server/app/main.py` with `tee -a`" → qa reports it
  was blocked; "use the backend subagent to add a comment to `server/app/main.py`" → allowed, and the
  `PostToolUse` Edit hook ran ruff and pytest (hook output visible in the subagent's report).
- Post-Bash check: a backend subagent runs `uv run ruff format server/app/main.py` after an edit that introduced
  a lint error elsewhere → the hook reports the ruff problem; a plain `ls` → no check, under 1 s.
- Pre-commit: on a throwaway branch, add `server/tests/unit/test_fail.py` with `assert False`, `git add`,
  `git commit -m "x"` → exits non-zero with the pytest failure; `git commit --no-verify` → denied by settings;
  delete the file, commit a docs-only change → no checks run, commit succeeds; branch deleted.
- `git config core.hooksPath` → `.githooks`; starting a session with it unset shows the `check_setup` warning.
- `python3 .claude/hooks/archive_conversation.py --audit` on this plan's own sessions → at least one `Agent`
  call of type `reviewer` (step 9) and zero shell writes into `server/` or `client/src`; the session Markdown
  lists "Subagents invoked".
- Reviewer: step 9 produced a report with the five checklist headings and a verdict; it made no file change
  (`git status` clean after it ran).
- Each agent file has `model:`; `@"reviewer (agent)" what is your model?` answers with the configured ID.

## Rollback

`git revert` the plan's commits (no data, no migrations). Then `git config --unset core.hooksPath`, delete
`.claude/.hook-state.json`. Restoring `qa_scope_guard.py` comes with the revert. If settings hooks turn out not
to fire inside subagents on this Claude Code version (contrary to the docs), the fallback is to add the same
`scope_guard.py` as a frontmatter `PreToolUse` hook in each agent file (one line each).

## Open questions (each with a suggested answer)

1. **Should the main session be blocked from editing `server/` and `client/src` at all?**
   → *Suggested:* yes. Six sessions with the delegation documented produced zero delegations; a rule in
   AGENTS.md plus an owner field would repeat that. The guard is the only thing that acts at the moment of the
   edit, and the cost is small: the main session keeps docs, plans, `.claude/`, README, CI. Escape hatch: a
   git-ignored marker file `.claude/main-edits.allow` that only Yosef creates (AGENTS.md says the agent never
   creates it); while it exists the guard logs instead of blocking.
2. **Models: full IDs or aliases, and Opus for the reviewer?**
   → *Suggested:* full IDs (`claude-sonnet-5-5`, `claude-opus-5-5`): "a defined model" that does not move
   when an alias is repointed; the showcase stays reproducible. Opus for the reviewer because it runs once per
   plan, is read-only, and its value is judgment across a diff and a dozen docs; the implementers stay on Sonnet
   because they run often and their work is checked by hooks and the reviewer.
3. **Which checks in the pre-commit hook for the client?**
   → *Suggested:* lint, typecheck, prettier `--check`, and `npm test` (asked for lint/typecheck; tests add 4.7 s
   and CI runs them anyway, so a commit that would fail CI is caught locally).
4. **Run the whole server suite after a Bash command that changed `.py` files, or only "relevant" tests?**
   → *Suggested:* the whole suite with `-x`: 9 s, no mapping to maintain, same as the Edit hook.
5. **Keep the `Explore`/`Plan`/`general-purpose` built-in agents writable?**
   → *Suggested:* treat any agent type not in the table like the main session (no source writes). Research
   agents don't write; `general-purpose` should not write source either.
6. **Should the reviewer also run the test suites?**
   → *Suggested:* no; Bash stays git-read-only as asked. The `qa` step before it reports test results, and the
   pre-commit hook and CI run them. The reviewer reads tests; it does not execute code.

## Amendment on approval

Yosef approved the plan on 2026-11-15 ("implement plan 006") without changes. Every open question below is
answered as suggested.

## Review

*(filled in by the reviewer step)*

## What changed vs. plan

*(filled in when the plan is closed)*
