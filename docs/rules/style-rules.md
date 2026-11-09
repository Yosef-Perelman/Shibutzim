# Style rules

Formatting is automated; humans and agents don't argue about it.

## Python

- **ruff** is both formatter and linter. Configuration lives in `server/pyproject.toml`.
- Line length 100. Double quotes. Imports sorted by ruff (`I` rules): standard library, third party, first party.
- Lint rule sets: `E`, `F`, `W`, `I`, `B` (bugbear), `UP` (pyupgrade), `SIM`, `DTZ` (no naive datetimes).
- `ruff format` and `ruff check --fix` run automatically after every `.py` edit (PostToolUse hook). Commit only
  code that passes `ruff check`.

## TypeScript

- **Prettier** for formatting, **ESLint** (typescript-eslint, react-hooks) for linting. Configuration in `client/`.
- Line length 100, single quotes, semicolons, trailing commas.
- `tsc --noEmit` must pass.

## Comments and docstrings

- Code says *what*; comments say *why*. Delete comments that repeat the code.
- Docstrings on public functions of pure modules and services, describing inputs, outputs and the rule they
  implement. Not on trivial functions.
- Link to the rule or doc when code implements a business rule: `# Work day = day the entry started
  (product-definition §6.1)`.

## Markdown

- One sentence per idea; tables for parallel facts; relative links between docs.
- Docs describe the current state. History belongs in plans and git.
