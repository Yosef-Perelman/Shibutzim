#!/usr/bin/env python3
"""PostToolUse feedback loop for TypeScript edits under client/.

After an Edit/Write of a `.ts` or `.tsx` file inside `client/`: `prettier --write` and `eslint --fix` on that file
(see `checks.py`). The file is recorded in `.claude/.hook-state.json` so `post_bash_check.py` does not check it
again. The type check and the Vitest suite are not run here: they are slow for an every-edit hook, so the
pre-commit hook runs `npm run typecheck && npm test` instead.

Remaining problems are printed to stderr with exit code 2, which Claude Code feeds back to the agent (the edit
itself has already happened). It is a no-op until `client/package.json` exists.

Written for the system Python (3.9+), standard library only.
"""
import json
import sys
from pathlib import Path

import checks


def main() -> None:
    event = json.load(sys.stdin)
    raw_path = (event.get("tool_input") or {}).get("file_path", "")
    project = checks.project_dir(event)
    path = Path(raw_path).resolve()
    if not raw_path or not checks.is_client_source(project, path):
        return

    problems = checks.check_client(project, [path])
    checks.record(project, [path])
    if problems:
        print("\n\n".join(problems), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
