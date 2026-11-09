#!/usr/bin/env python3
"""PostToolUse feedback loop for Python edits under server/.

After an Edit/Write of a `.py` file inside `server/`:
1. `ruff format <file>` and `ruff check --fix <file>`;
2. `pytest -q -x` for the whole server suite (stop at the first failure, 60 s limit).

Problems are printed to stderr with exit code 2, which Claude Code feeds back to the agent
(the edit itself has already happened). It is a no-op until `server/pyproject.toml` exists.

Written for the system Python (3.9+), standard library only.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PYTEST_TIMEOUT_SECONDS = 60
MAX_OUTPUT_LINES = 60
PYTEST_NO_TESTS_COLLECTED = 5


def tail(text: str) -> str:
    lines = text.strip().splitlines()
    return "\n".join(lines[-MAX_OUTPUT_LINES:])


def run(command: list, cwd: Path, timeout: int = PYTEST_TIMEOUT_SECONDS):
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def main() -> None:
    event = json.load(sys.stdin)
    raw_path = (event.get("tool_input") or {}).get("file_path", "")
    if not raw_path.endswith(".py"):
        return

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".").resolve()
    server_dir = project_dir / "server"
    path = Path(raw_path).resolve()
    if server_dir not in path.parents or not (server_dir / "pyproject.toml").exists():
        return

    uv = shutil.which("uv")
    if uv is None:
        print("post-edit hook: `uv` not found, so ruff and pytest did not run. "
              "Install it with `brew install uv`.", file=sys.stderr)
        sys.exit(2)

    problems = []

    run([uv, "run", "ruff", "format", str(path)], server_dir)
    lint = run([uv, "run", "ruff", "check", "--fix", str(path)], server_dir)
    if lint.returncode != 0:
        problems.append("ruff check found problems it could not fix:\n" + tail(lint.stdout + lint.stderr))

    try:
        tests = run([uv, "run", "pytest", "-q", "-x"], server_dir)
        if tests.returncode not in (0, PYTEST_NO_TESTS_COLLECTED):
            problems.append("pytest failed:\n" + tail(tests.stdout + tests.stderr))
    except subprocess.TimeoutExpired:
        problems.append(
            f"pytest exceeded {PYTEST_TIMEOUT_SECONDS}s. The suite is too slow for an every-edit hook; "
            "see plan 000, open question 1."
        )

    if problems:
        print("\n\n".join(problems), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
