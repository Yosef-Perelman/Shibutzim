# Git rules

The commit history is part of the showcase: it should read **docs → plan → tests → code** for every feature.

## Commits

- [Conventional Commits](https://www.conventionalcommits.org/): `type: summary` in the imperative, ≤ 72 chars.

  | Type | Use |
  |---|---|
  | `docs` | docs and rules |
  | `plan` | adding, amending or closing a plan, roadmap updates |
  | `test` | tests only |
  | `feat` | new behavior |
  | `fix` | bug fix (preceded or accompanied by its test) |
  | `refactor` | no behavior change |
  | `chore` | tooling, config, dependencies, guardrails |

- One logical change per commit. Within a plan, each step is one commit where practical.
- Stage explicit paths (`git add <paths>`), not `git add -A`, so ignored or unrelated files are never swept in.
- The body explains *why* when it isn't obvious; reference the plan (`Plan 001, step 4`).

## Branches

- Plan 000 is committed directly on `main`.
- From plan 001: one branch per plan, `plan/NNN-short-name`, created from `main` when the approved plan is
  committed. The approval commit is the branch's first commit.
- **When:** the branch is merged when the plan closes – after validation passes and the closing commit
  (`plan: close plan NNN`) is on the branch – and before the next plan is drafted.
- **How:** locally, with a merge commit and no squash or rebase:

  ```bash
  git switch main
  git merge --no-ff plan/NNN-short-name -m "Merge plan NNN – <name>"
  git branch -d plan/NNN-short-name
  ```

- **Why a merge commit:** every commit of the plan stays in `main`'s history, and the merge commit marks where the
  plan ends. `git log --first-parent main` shows one line per plan; `git log main` shows every step.

## Never

- Never force-push (`--force`, `-f`, `--force-with-lease`) or rewrite published history. (Denied in settings.)
- Never commit `.env`, secrets, the local planning brief, or generated files (`node_modules`, `__pycache__`,
  `dist`).
- Never push without the human asking for it.
- Never commit code that fails `ruff check` or the test suite.
