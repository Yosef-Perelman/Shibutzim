#!/usr/bin/env python3
"""PostToolUse feedback loop for TypeScript edits under client/.

After an Edit/Write of a `.ts` or `.tsx` file inside `client/`:
1. `prettier --write <file>`;
2. `eslint --fix <file>`.

Remaining lint problems are printed to stderr with exit code 2, which Claude Code feeds back to the agent
(the edit itself has already happened). The type check and the Vitest suite are not run here: they are slow for
an every-edit hook, so `npm run typecheck && npm test` run before each commit instead (plan 003, open
question 10). It is a no-op until `client/package.json` exists.

Written for the system Python (3.9+), standard library only.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

TIMEOUT_SECONDS = 60
MAX_OUTPUT_LINES = 60
EXTENSIONS = {".ts", ".tsx"}
SKIPPED_DIRECTORIES = {"node_modules", "dist"}


def tail(text: str) -> str:
    lines = text.strip().splitlines()
    return "\n".join(lines[-MAX_OUTPUT_LINES:])


def run(command: list, cwd: Path):
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)


def main() -> None:
    event = json.load(sys.stdin)
    raw_path = (event.get("tool_input") or {}).get("file_path", "")
    path = Path(raw_path)
    if path.suffix not in EXTENSIONS:
        return

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".").resolve()
    client_dir = project_dir / "client"
    path = path.resolve()
    if client_dir not in path.parents or not (client_dir / "package.json").exists():
        return
    if SKIPPED_DIRECTORIES & set(path.relative_to(client_dir).parts):
        return

    bin_dir = client_dir / "node_modules" / ".bin"
    prettier, eslint = bin_dir / "prettier", bin_dir / "eslint"
    if not prettier.exists() or not eslint.exists():
        print("post-edit hook: client dependencies are missing, so Prettier and ESLint did not run. "
              "Run `npm install` in client/.", file=sys.stderr)
        sys.exit(2)

    problems = []
    try:
        format_result = run([str(prettier), "--write", str(path)], client_dir)
        if format_result.returncode != 0:
            problems.append("prettier could not format the file:\n" + tail(format_result.stdout + format_result.stderr))
        lint = run([str(eslint), "--fix", str(path)], client_dir)
        if lint.returncode != 0:
            problems.append("eslint found problems it could not fix:\n" + tail(lint.stdout + lint.stderr))
    except subprocess.TimeoutExpired:
        problems.append(f"Prettier or ESLint exceeded {TIMEOUT_SECONDS}s.")

    if problems:
        print("\n\n".join(problems), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
