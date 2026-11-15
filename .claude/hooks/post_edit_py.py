#!/usr/bin/env python3
"""PostToolUse feedback loop for Python edits under server/.

After an Edit/Write of a `.py` file inside `server/`: `ruff format`, `ruff check --fix` on that file, then
`pytest -q -x` for the whole server suite (see `checks.py`; 60 s limit, measured about 9 s). The file is recorded
in `.claude/.hook-state.json` so `post_bash_check.py` does not check it again.

Problems are printed to stderr with exit code 2, which Claude Code feeds back to the agent (the edit itself has
already happened). It is a no-op until `server/pyproject.toml` exists.

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
    if not raw_path or not checks.is_server_python(project, path):
        return

    problems = checks.check_python(project, [path])
    checks.record(project, [path])
    if problems:
        print("\n\n".join(problems), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
