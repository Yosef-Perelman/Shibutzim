#!/usr/bin/env python3
"""PostToolUse feedback loop for Bash commands that changed source files.

The Edit/Write hooks never see a file written by a shell command (`sed -i`, a heredoc, `git checkout`, a code
generator). After every Bash command this hook lists the dirty files (`git status --porcelain`), keeps those whose
modification time differs from `.claude/.hook-state.json`, and for those runs the same checks as the Edit hooks
(see `checks.py`): ruff and the whole pytest suite for `server/**/*.py`, Prettier and ESLint for
`client/**/*.ts(x)`. A plain `ls` finds nothing new and costs one `git status`.

Problems are printed to stderr with exit code 2 (the command has already run), which Claude Code feeds back to
the agent. Written for the system Python (3.9+), standard library only.
"""
import json
import sys

import checks


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return
    if (event.get("tool_response") or {}).get("interrupted"):
        return
    project = checks.project_dir(event)
    changed = checks.changed_files(project)
    python_files = [p for p in changed if checks.is_server_python(project, p)]
    client_files = [p for p in changed if checks.is_client_source(project, p)]
    if not python_files and not client_files:
        return

    checks.start_budget()
    problems = checks.check_python(project, python_files) + checks.check_client(project, client_files)
    checks.record(project, python_files + client_files)
    if problems:
        print("\n\n".join(problems), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
