"""Shared code of the post-edit and post-Bash feedback hooks.

- `check_python(project, files)`: `ruff format`, `ruff check --fix`, then the whole `pytest -q -x` suite.
- `check_client(project, files)`: `prettier --write` and `eslint --fix`.
- A small state file, `.claude/.hook-state.json` (git-ignored), maps each checked file to the modification time it
  had right after its check, so a file is not checked twice: not by the Edit hook and then again by the Bash
  hook, and not on every later Bash command.

Both checkers return a list of problem texts (empty when everything is fine); the hooks print them to stderr
with exit code 2, which Claude Code feeds back to the agent. Written for the system Python (3.9+), standard
library only.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional

STATE_FILE = Path(".claude", ".hook-state.json")
PYTEST_TIMEOUT_SECONDS = 60
NODE_TIMEOUT_SECONDS = 60
GIT_TIMEOUT_SECONDS = 10
MAX_OUTPUT_LINES = 60
PYTEST_NO_TESTS_COLLECTED = 5
CLIENT_EXTENSIONS = {".ts", ".tsx"}
CLIENT_SKIPPED_DIRECTORIES = {"node_modules", "dist"}
# The text of tests/conftest.py DB_UNREACHABLE, up to the part that varies.
DB_UNREACHABLE_MARKER = "Database not reachable"
DB_UNREACHABLE_HINT = (
    "The database is not reachable, so pytest could not run: start it with `docker compose up -d db`, then retry."
)


def project_dir(event: dict) -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".").resolve()


def tail(text: str) -> str:
    lines = text.strip().splitlines()
    return "\n".join(lines[-MAX_OUTPUT_LINES:])


def run(command: List[str], cwd: Path, timeout: int) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)


# --- Which files are server or client source ------------------------------------------------------------


def is_server_python(project: Path, path: Path) -> bool:
    return path.suffix == ".py" and (project / "server") in path.parents and not (
        CLIENT_SKIPPED_DIRECTORIES | {"__pycache__", ".venv"}
    ) & set(path.relative_to(project / "server").parts)


def is_client_source(project: Path, path: Path) -> bool:
    client = project / "client"
    return (
        path.suffix in CLIENT_EXTENSIONS
        and client in path.parents
        and not CLIENT_SKIPPED_DIRECTORIES & set(path.relative_to(client).parts)
    )


# --- State: files already checked -----------------------------------------------------------------------


def load_state(project: Path) -> Dict[str, int]:
    try:
        data = json.loads((project / STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, int)} if isinstance(data, dict) else {}


def mtime_ns(path: Path) -> Optional[int]:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


def record(project: Path, paths: Iterable[Path]) -> None:
    """Remember the current modification time of each file as 'checked'."""
    state = load_state(project)
    for path in paths:
        stamp = mtime_ns(path)
        if stamp is not None:
            state[path.resolve().relative_to(project).as_posix()] = stamp
    target = project / STATE_FILE
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")
    except OSError:
        pass


def changed_files(project: Path) -> List[Path]:
    """Files git lists as modified or untracked whose modification time differs from the recorded one."""
    try:
        result = run(["git", "status", "--porcelain", "-z", "-uall"], project, GIT_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    state = load_state(project)
    entries = result.stdout.split("\0")
    found: List[Path] = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        status, relative = entry[:2], entry[3:]
        if "R" in status or "C" in status:
            index += 1  # the next entry is the original path
        path = (project / relative).resolve()
        stamp = mtime_ns(path)
        if stamp is None or not path.is_file():
            continue
        if state.get(path.relative_to(project).as_posix()) != stamp:
            found.append(path)
    return found


# --- Checkers --------------------------------------------------------------------------------------------


def check_python(project: Path, files: List[Path]) -> List[str]:
    server = project / "server"
    if not files or not (server / "pyproject.toml").exists():
        return []
    uv = shutil.which("uv")
    if uv is None:
        return ["`uv` not found, so ruff and pytest did not run. Install it with `brew install uv`."]

    problems: List[str] = []
    names = [str(path) for path in files]
    run([uv, "run", "ruff", "format", *names], server, PYTEST_TIMEOUT_SECONDS)
    lint = run([uv, "run", "ruff", "check", "--fix", *names], server, PYTEST_TIMEOUT_SECONDS)
    if lint.returncode != 0:
        problems.append("ruff check found problems it could not fix:\n" + tail(lint.stdout + lint.stderr))

    try:
        tests = run([uv, "run", "pytest", "-q", "-x"], server, PYTEST_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        problems.append(
            f"pytest exceeded {PYTEST_TIMEOUT_SECONDS}s. The suite normally takes about 10 s: look for a hanging "
            "test or a database that does not answer (`docker compose ps`), then run `uv run pytest -q -x` by hand."
        )
        return problems
    output = tests.stdout + tests.stderr
    if tests.returncode not in (0, PYTEST_NO_TESTS_COLLECTED):
        problems.append(DB_UNREACHABLE_HINT if DB_UNREACHABLE_MARKER in output else "pytest failed:\n" + tail(output))
    return problems


def check_client(project: Path, files: List[Path]) -> List[str]:
    client = project / "client"
    if not files or not (client / "package.json").exists():
        return []
    bin_dir = client / "node_modules" / ".bin"
    prettier, eslint = bin_dir / "prettier", bin_dir / "eslint"
    if not prettier.exists() or not eslint.exists():
        return ["Client dependencies are missing, so Prettier and ESLint did not run. Run `npm install` in client/."]

    problems: List[str] = []
    names = [str(path) for path in files]
    try:
        formatted = run([str(prettier), "--write", *names], client, NODE_TIMEOUT_SECONDS)
        if formatted.returncode != 0:
            problems.append("prettier could not format the file:\n" + tail(formatted.stdout + formatted.stderr))
        lint = run([str(eslint), "--fix", *names], client, NODE_TIMEOUT_SECONDS)
        if lint.returncode != 0:
            problems.append("eslint found problems it could not fix:\n" + tail(lint.stdout + lint.stderr))
    except subprocess.TimeoutExpired:
        problems.append(f"Prettier or ESLint exceeded {NODE_TIMEOUT_SECONDS}s.")
    return problems
