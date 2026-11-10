#!/usr/bin/env python3
"""PreToolUse guard for file tools.

Blocks (exit code 2, reason on stderr):
- reading or editing `.env` and `.env.*` files, except `.env.example`;
- editing or overwriting an Alembic migration under `server/alembic/versions/` that git already tracks.
  A freshly generated, uncommitted migration may still be corrected by hand, as database-rules require;
  once committed it is frozen and a mistake needs a new migration.

Written for the system Python (3.9+), standard library only.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
MIGRATIONS_DIR = Path("server", "alembic", "versions")


def is_env_file(path: Path) -> bool:
    name = path.name
    if name == ".env.example":
        return False
    return name == ".env" or name.startswith(".env.")


def is_tracked_by_git(path: Path, project_dir: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(path)],
            cwd=project_dir,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        # If git cannot answer, err on the side of protecting the file.
        return True
    return result.returncode == 0


def is_committed_migration(path: Path, project_dir: Path) -> bool:
    try:
        relative = path.resolve().relative_to(project_dir.resolve())
    except ValueError:
        return False
    if relative.parent != MIGRATIONS_DIR or path.suffix != ".py":
        return False
    return path.exists() and is_tracked_by_git(path, project_dir)


def block(reason: str) -> None:
    print(reason, file=sys.stderr)
    sys.exit(2)


def main() -> None:
    event = json.load(sys.stdin)
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    raw_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw_path:
        return

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".")
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path(event.get("cwd") or project_dir) / path

    if is_env_file(path):
        block(
            f"Blocked: {path.name} may hold secrets and is off-limits to agents. "
            "Use .env.example to document variables (AGENTS.md, guardrails)."
        )

    if tool in EDIT_TOOLS and is_committed_migration(path, project_dir):
        block(
            f"Blocked: {path.name} is a committed Alembic migration and must never be edited. "
            "Create a new migration instead (docs/rules/database-rules.md)."
        )


if __name__ == "__main__":
    main()
