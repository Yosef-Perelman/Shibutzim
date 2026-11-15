#!/usr/bin/env python3
"""SessionStart hook: warn the agent (and so the user) when the local setup is incomplete.

Checks that `git config core.hooksPath` is `.githooks` (so the committed pre-commit hook runs), that `uv` is
installed, and that `client/node_modules/.bin` exists. Prints nothing when all is well; otherwise it adds the
warnings to the session as `additionalContext`. Never blocks: the exit code is always 0.

Written for the system Python (3.9+), standard library only.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def hooks_path(project: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "config", "--get", "core.hooksPath"], cwd=project, capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip()


def warnings_for(project: Path) -> list:
    found = []
    if hooks_path(project) != ".githooks":
        found.append(
            "Git hooks are not enabled in this clone, so the pre-commit lint and tests will not run. "
            "Ask the user to run `git config core.hooksPath .githooks`."
        )
    if shutil.which("uv") is None:
        found.append("`uv` is not installed, so the server checks cannot run. Install it with `brew install uv`.")
    if (project / "client" / "package.json").exists() and not (project / "client" / "node_modules" / ".bin").exists():
        found.append("Client dependencies are missing. Run `npm install` in client/.")
    return found


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        event = {}
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".").resolve()
    found = warnings_for(project)
    if found:
        text = "Setup warnings:\n" + "\n".join(f"- {line}" for line in found)
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 – a hook must never block Claude Code
        print(f"check_setup: {type(error).__name__}: {error}", file=sys.stderr)
    sys.exit(0)
