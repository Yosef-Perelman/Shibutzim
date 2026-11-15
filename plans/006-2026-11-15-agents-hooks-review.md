# Plan 006 – Agents and hooks

| | |
|---|---|
| **Status** | done |
| **Date** | 2026-11-15 |
| **Related docs** | [AGENTS.md](../AGENTS.md), [planning-rules](../docs/rules/planning-rules.md), [git-rules](../docs/rules/git-rules.md), [testing-rules](../docs/rules/testing-rules.md), [README](../README.md) §"How this was built with AI" |
| **Roadmap** | plan 006 of 007 |
| **Branch** | plan/006-agents-hooks-review |

## Goal

Every source change in this repository is made by the right subagent and checked by hooks whatever tool wrote the
file. After this plan: a shell write into `server/` or `client/src` is blocked for every agent; ruff and the tests
run after Bash commands that changed files; a committed git pre-commit hook rejects a commit that fails lint or
tests regardless of how the files were written; each agent has a defined model; and the plan template names an
owner for every step, so delegation is visible in the plan, enforced by a hook, and auditable from the session
transcripts.

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
   `client/`, main session and any other agent → no writes under `server/` or `client/src/` (docs, plans,
   `.claude/`, `README.md`, `.github/`, `client/` config files stay editable).
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
5. **Subagent use made real**: (a) AGENTS.md rule: the main session plans, delegates and edits docs, plans and
   `.claude/`; source changes under `server/` and `client/src` are made by `backend`/`frontend`, tests by `qa`;
   (b) the scope guard enforces it (item 1); (c) the plan template names an owner per step (item 7); (d) the
   closing checklist includes a subagent audit; (e) `archive_conversation.py` also copies `subagents/*.jsonl` +
   `.meta.json` into `conversations/raw/<date>-<session>/subagents/`, renders a "Subagents invoked" list in the
   Markdown, and gains `--audit [transcript…]` that prints per session: `Agent` calls by `subagent_type`, and
   Bash commands that wrote source via shell. The table above is its first output.
6. **`model:` per agent**: `claude-sonnet-5-5` for `backend`, `frontend`, `qa` (open question 2).
7. **`new-plan` skill and template**: every step is `N. **owner** – text` with owner ∈ `backend`, `frontend`,
   `qa`, `main`; tests-first ordering stays (a `qa` step precedes the `backend`/`frontend` step it tests); the
   last step is always `main` – close. `planning-rules.md` ("Writing a good plan", "Closing a plan") and
   `SKILL.md` steps 4 and 6 are updated; the closing checklist adds: `--audit` run and its numbers noted in
   "What changed vs. plan".
8. Docs: AGENTS.md (guardrails, subagents table with models, common commands, the delegation rule), README
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
    full model ID such as `claude-sonnet-5-5`, or `inherit`; also `tools`, `disallowedTools`, `permissionMode`,
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
- Assumed: `claude-sonnet-5-5` is a valid full ID for this account (it is the ID the drafting session reports); if
  a subagent fails to start, fall back to the alias `sonnet`.

## Steps

1. **main** – `test:` hook tests first: `.claude/hooks/tests/test_scope_guard.py`,
   `test_post_bash_check.py`, `test_archive_audit.py` (stdlib `unittest`, run with
   `python3 -m unittest discover -s .claude/hooks/tests`): each test feeds a hook-event JSON on stdin and asserts
   exit code and message. Cases: `cat > server/app/x.py <<'EOF'` blocked for main; same with `agent_type: backend`
   allowed; `python3 - <<EOF` mentioning `client/src/App.tsx` blocked; `uv run ruff format .` allowed;
   `git restore server/app/x.py` allowed; `qa` writing `server/app/x.py` via Edit and via `tee` blocked,
   `server/tests/x.py` allowed; `frontend` blocked on `server/`; main allowed on `plans/`, `docs/`, `.claude/`;
   `--audit` on a fixture transcript counts 1 Agent call of type `qa` and 2 shell writes.
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
7. **main** – `docs:` planning template and rules (owner per step, closing checklist), `new-plan/SKILL.md`,
   AGENTS.md (delegation rule, guardrails, subagents table, commands), README §"How this was built" 4–5 and "Run
   it locally", `git-rules.md`.
8. **main** – run Validation, fill "What changed vs. plan", close and merge (planning-rules "Closing a plan").

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
- `python3 .claude/hooks/archive_conversation.py --audit` on this plan's own sessions → zero shell writes into
  `server/` or `client/src`; the session Markdown lists "Subagents invoked".
- Each agent file has `model:`.

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
2. **Models: full IDs or aliases?**
   → *Suggested:* full IDs (`claude-sonnet-5-5`): "a defined model" that does not move when an alias is
   repointed; the showcase stays reproducible. The implementers stay on Sonnet because they run often and their
   work is checked by hooks.
3. **Which checks in the pre-commit hook for the client?**
   → *Suggested:* lint, typecheck, prettier `--check`, and `npm test` (asked for lint/typecheck; tests add 4.7 s
   and CI runs them anyway, so a commit that would fail CI is caught locally).
4. **Run the whole server suite after a Bash command that changed `.py` files, or only "relevant" tests?**
   → *Suggested:* the whole suite with `-x`: 9 s, no mapping to maintain, same as the Edit hook.
5. **Keep the `Explore`/`Plan`/`general-purpose` built-in agents writable?**
   → *Suggested:* treat any agent type not in the table like the main session (no source writes). Research
   agents don't write; `general-purpose` should not write source either.

## Amendment on approval

Yosef approved the plan on 2026-11-15 ("implement plan 006") without changes. Every open question above is
answered as suggested.

## What changed vs. plan

- **Scope reduced after implementation (2026-11-15).** Yosef removed one item: a read-only review subagent, with
  its own Bash guard, a review step at the end of every plan and a review section in the template. It ran for a
  long time and cost many tokens. Its agent file, guard, tests, rule-table row and every doc mention were deleted;
  the scope, steps, validation and open questions above no longer contain it.
- **Shell writes by `backend`/`frontend`.** The Goal says blocked for every agent, the step-1 tests say `backend`
  may write `server/` by shell. The code follows the tests: one table for Edit and Bash. Those writes are checked
  afterwards by the post-Bash hook.
- **`docs/`.** `backend` and `frontend` may also write `docs/`, because `backend.md` tells the backend agent to
  update the glossary and architecture in the same step.
- **Allowlist.** Broader than listed: any `git`, `npx`, `npm`, `pnpm`, `yarn`, `ruff`, `prettier`, `eslint`,
  `alembic` command skips the command-specific write detection (redirects are still checked).
- **Guard extras beyond the plan:** variable expansion, `bash -c` and heredoc-to-shell, scripts piped into an
  interpreter, `xargs`/`find -exec`/`find -delete`/`timeout`, multi-file `sed -i`, redirects glued to a word,
  case-insensitive paths (macOS), a worktree prefix under `.claude/worktrees/` (layout not verified), the
  escape-hatch file off limits to every agent, and generated-path exemptions limited to caches, `client/dist`,
  `client/node_modules` and `server/static`.
- **Also added:** `check_setup.py` baselines source files that are already dirty at session start, so the post-Bash
  hook does not reformat work in progress; a shared time budget (105 s) in `checks.py`, below the 120 s hook
  limit; guarded input and project-relative paths in the post hooks; symlink-safe state keys. Pre-commit counts
  deletions, handles non-ASCII paths, and runs the hook tests when `.claude/hooks/` is staged.
- **Not done:** deny rules for `git commit -an`, `git -c core.hooksPath=… commit` and
  `git config --unset core.hooksPath` (permission changes beyond the plan; for Yosef to decide). The two forms
  the plan names are denied (checked live).
- **`--audit` numbers differ from the Goal table.** The Goal table was an earlier hand count. `--audit` counts
  main-conversation tool calls once per id, and a command counts when it writes under `server/` or `client/src/`.
  It counts attempts, including ones the guard blocked:

  | Session | Agent calls | Bash | Edit/Write | Shell source writes |
  |---|---|---|---|---|
  | 2026-11-10 5875b1be | 0 | 130 | 3 | 47 |
  | 2026-11-10 e2ef46c5 | 0 | 35 | 1 | 2 |
  | 2026-11-11 855d1f2f | 0 | 134 | 5 | 45 |
  | 2026-11-11 871597cc | 0 | 86 | 0 | 39 |
  | 2026-11-11 f530bcf0 | 0 | 154 | 2 | 57 |
  | 2026-11-12 57060ed8 | 0 | 165 | 53 | 14 |
  | **Plans 000–005** | **0** | **704** | **64** | **204** |

  This plan's implementing session (`2ce8ac82`): qa 2, backend 1 and general-purpose 1 Agent calls (plus one call
  of the removed agent type that never started); 4 shell-write attempts, all blocked by the guard; no change
  under `server/` or `client/` on the branch. The drafting session (`965b6377`): Explore 2, qa 1, no shell writes.
- **Validation results so far.**
  - Hook tests pass.
  - Live, main session: `cat > server/app/x.py <<EOF` blocked and no file created; `Edit` of `server/app/main.py`
    blocked (message names `backend`); `uv run ruff format --check .` in `server/` ran.
  - Live, subagents: `qa` with `tee -a` on `server/app/main.py` blocked; `qa` could write `server/tests/…`;
    `backend` could `rm` a file in `server/tests/` and edit `server/app/main.py`, and the post-edit hook recorded it
    (the change was reverted).
  - Pre-commit on a throwaway branch (deleted): a failing test under `server/tests/` was rejected with exit 1 (ruff
    B011 fired before pytest); `git commit --no-verify` and `git commit -n` were both denied by `settings.json`;
    a docs-only commit ran no checks (0.04 s).
  - `git config core.hooksPath` is `.githooks`. The session-start warning is covered by a unit test, not by starting
    a session with it unset.
  - A clean-tree post-Bash check takes 0.03 s. The "lint error elsewhere" live scenario was covered by unit tests
    only.
  - `archive_conversation.py --audit` lists agent types and shell writes; the session Markdown has "Subagents
    invoked".

## Closing note

Closed 2026-11-15 after Yosef's go. Final checks on the branch: hook tests 77 pass, `uv run ruff check .` clean,
server tests 1076 pass, client lint and typecheck pass. The deny rules for the extra commit-skipping forms were not
added and stay for Yosef to decide.
