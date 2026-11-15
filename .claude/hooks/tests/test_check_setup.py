"""Tests for check_setup.py: the SessionStart warnings."""
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from hook_helpers import HOOKS_DIR, HookTestCase


class CheckSetupTests(HookTestCase):
    def setUp(self) -> None:
        super().setUp()
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        self.bin = self.project / "bin"
        self.bin.mkdir()
        (self.bin / "git").symlink_to(shutil.which("git"))
        (self.project / "client" / "package.json").write_text("{}")

    def run_hook(self, with_uv: bool = True, with_node_modules: bool = True) -> str:
        if with_uv:
            (self.bin / "uv").write_text("#!/bin/sh\n")
            (self.bin / "uv").chmod(0o755)
        if with_node_modules:
            (self.project / "client" / "node_modules" / ".bin").mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.project), PATH=str(self.bin))
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "check_setup.py")],
            input=json.dumps({"hook_event_name": "SessionStart"}), capture_output=True, text=True, env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_everything_in_place_prints_nothing(self):
        subprocess.run(["git", "config", "core.hooksPath", ".githooks"], cwd=self.project, check=True)
        self.assertEqual(self.run_hook(), "")

    def test_hooks_path_not_set_warns_with_the_command(self):
        output = json.loads(self.run_hook())
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("git config core.hooksPath .githooks", context)

    def test_missing_uv_and_node_modules_are_reported(self):
        subprocess.run(["git", "config", "core.hooksPath", ".githooks"], cwd=self.project, check=True)
        context = json.loads(self.run_hook(with_uv=False, with_node_modules=False))
        text = context["hookSpecificOutput"]["additionalContext"]
        self.assertIn("uv", text)
        self.assertIn("npm install", text)
        self.assertNotIn("core.hooksPath", text)


if __name__ == "__main__":
    unittest.main()
