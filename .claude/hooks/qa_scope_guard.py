#!/usr/bin/env python3
"""PreToolUse guard registered only in the qa subagent's frontmatter.

The qa agent may write only tests and evals:
- anything under `server/tests/` or `server/evals/`;
- client test files: `client/**/*.test.ts(x)` and `client/**/*.spec.ts(x)`.
Any other Edit/Write is blocked with exit code 2.

Written for the system Python (3.9+), standard library only.
"""
import json
import os
import re
import sys
from pathlib import Path

ALLOWED_DIRS = (Path("server", "tests"), Path("server", "evals"))
CLIENT_TEST_FILE = re.compile(r"^client/.+\.(test|spec)\.tsx?$")


def is_allowed(relative: Path) -> bool:
    if any(allowed == relative or allowed in relative.parents for allowed in ALLOWED_DIRS):
        return True
    return bool(CLIENT_TEST_FILE.match(relative.as_posix()))


def main() -> None:
    event = json.load(sys.stdin)
    tool_input = event.get("tool_input") or {}
    raw_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw_path:
        return

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".").resolve()
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path(event.get("cwd") or project_dir) / path
    try:
        relative = path.resolve().relative_to(project_dir)
    except ValueError:
        relative = None

    if relative is None or not is_allowed(relative):
        print(
            f"Blocked: the qa agent may only write under server/tests/, server/evals/ or client "
            f"*.test/*.spec files, not {raw_path}. Report the needed source change instead.",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
