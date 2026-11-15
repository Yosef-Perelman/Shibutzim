"""Shared helpers for the hook tests: run a hook script the way Claude Code does (event JSON on stdin)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, Optional, Tuple

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))


def make_project() -> Path:
    """A throwaway project directory with the folders the hooks care about."""
    project = Path(tempfile.mkdtemp(prefix="shibutzim-hooks-")).resolve()
    for folder in ("server/app", "server/tests", "server/evals", "client/src", "docs", "plans", ".claude"):
        (project / folder).mkdir(parents=True, exist_ok=True)
    return project


def run_hook(
    script: str,
    event: dict,
    project: Path,
    env: Optional[Dict[str, str]] = None,
) -> Tuple[int, str]:
    """Run `.claude/hooks/<script>` with `event` on stdin; return (exit code, stderr)."""
    full_env = dict(os.environ)
    full_env["CLAUDE_PROJECT_DIR"] = str(project)
    full_env.update(env or {})
    result = subprocess.run(
        [sys.executable, str(HOOKS_DIR / script)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=full_env,
        cwd=str(project),
        timeout=60,
    )
    return result.returncode, result.stderr


class HookTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.project = make_project()

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.project, ignore_errors=True)
