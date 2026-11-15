"""Tests for post_bash_check.py and the shared checks.py state: ruff, pytest, prettier and eslint run after a
Bash command only for files that changed since the last check."""
import json
import os
import stat
import subprocess
import unittest
from pathlib import Path

from hook_helpers import HookTestCase, run_hook

DB_MESSAGE = "Database not reachable – run `docker compose up -d db` (then retry): connection refused"

FAKE_UV = """#!/bin/bash
echo "uv $*" >> "$FAKE_LOG"
case "$*" in
  *pytest*) [ -n "$FAKE_PYTEST_SLEEP" ] && exec sleep "$FAKE_PYTEST_SLEEP"; echo "$FAKE_PYTEST_OUT"; exit "${FAKE_PYTEST_CODE:-0}" ;;
  *"ruff check"*) echo "$FAKE_RUFF_OUT"; exit "${FAKE_RUFF_CODE:-0}" ;;
esac
exit 0
"""

FAKE_NODE_TOOL = """#!/bin/bash
echo "{name} $*" >> "$FAKE_LOG"
echo "$FAKE_{upper}_OUT"
exit "${{FAKE_{upper}_CODE:-0}}"
"""


class PostBashTestCase(HookTestCase):
    def setUp(self) -> None:
        super().setUp()
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        (self.project / "server" / "pyproject.toml").write_text("[project]\nname='x'\n")
        (self.project / "client" / "package.json").write_text("{}")
        self.log = self.project / "fake.log"
        self.log.write_text("")
        self.fakebin = self.project / "fakebin"
        self.fakebin.mkdir()
        self.install(self.fakebin / "uv", FAKE_UV)
        node_bin = self.project / "client" / "node_modules" / ".bin"
        node_bin.mkdir(parents=True)
        for name in ("prettier", "eslint"):
            self.install(node_bin / name, FAKE_NODE_TOOL.format(name=name, upper=name.upper()))
        self.env = {"PATH": f"{self.fakebin}{os.pathsep}{os.environ['PATH']}", "FAKE_LOG": str(self.log)}

    @staticmethod
    def install(path: Path, text: str) -> None:
        path.write_text(text)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def bash_event(self, command: str = "ls") -> dict:
        return {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "tool_response": {"stdout": "", "stderr": "", "interrupted": False},
            "cwd": str(self.project),
        }

    def run_check(self, **extra_env: str):
        return run_hook("post_bash_check.py", self.bash_event(), self.project, {**self.env, **extra_env})

    def calls(self) -> list:
        return [line for line in self.log.read_text().splitlines() if line]

    def write(self, relative: str, text: str = "x = 1\n") -> Path:
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path


class ServerChecksTests(PostBashTestCase):
    def test_clean_tree_runs_nothing(self):
        code, stderr = self.run_check()
        self.assertEqual((code, self.calls()), (0, []), stderr)

    def test_changed_python_file_gets_ruff_and_the_whole_suite(self):
        self.write("server/app/a.py")
        code, stderr = self.run_check()
        self.assertEqual(code, 0, stderr)
        joined = "\n".join(self.calls())
        self.assertIn("ruff format", joined)
        self.assertIn("ruff check --fix", joined)
        self.assertIn("pytest -q -x", joined)

    def test_unchanged_file_is_not_checked_twice(self):
        self.write("server/app/a.py")
        self.run_check()
        self.log.write_text("")
        code, _ = self.run_check()
        self.assertEqual((code, self.calls()), (0, []))
        self.assertTrue((self.project / ".claude" / ".hook-state.json").exists())

    def test_file_modified_after_the_last_check_is_checked_again(self):
        path = self.write("server/app/a.py")
        self.run_check()
        self.log.write_text("")
        stat_result = path.stat()
        os.utime(path, ns=(stat_result.st_atime_ns, stat_result.st_mtime_ns + 5_000_000_000))
        self.run_check()
        self.assertIn("pytest", "\n".join(self.calls()))

    def test_failing_tests_exit_2_with_the_output(self):
        self.write("server/app/a.py")
        code, stderr = self.run_check(FAKE_PYTEST_CODE="1", FAKE_PYTEST_OUT="FAILED tests/test_a.py::test_x")
        self.assertEqual(code, 2)
        self.assertIn("pytest failed", stderr)
        self.assertIn("FAILED tests/test_a.py::test_x", stderr)

    def test_ruff_problem_exits_2(self):
        self.write("server/app/a.py")
        code, stderr = self.run_check(FAKE_RUFF_CODE="1", FAKE_RUFF_OUT="a.py:1:1: F401 unused import")
        self.assertEqual(code, 2)
        self.assertIn("ruff", stderr)
        self.assertIn("F401", stderr)

    def test_unreachable_database_gives_one_line_hint(self):
        self.write("server/app/a.py")
        noisy = "\n".join(f"traceback line {n}" for n in range(40)) + "\n" + DB_MESSAGE
        code, stderr = self.run_check(FAKE_PYTEST_CODE="1", FAKE_PYTEST_OUT=noisy)
        self.assertEqual(code, 2)
        self.assertIn("docker compose up -d db", stderr)
        self.assertNotIn("traceback line", stderr)
        self.assertEqual(len(stderr.strip().splitlines()), 1)

    def test_non_source_files_are_ignored(self):
        self.write("docs/x.md", "hello")
        self.write("plans/p.md", "hello")
        self.write("server/pyproject.toml", "[project]\nname='y'\n")
        code, _ = self.run_check()
        self.assertEqual((code, self.calls()), (0, []))

    def test_slow_pytest_gives_a_timeout_message_instead_of_a_crash(self):
        self.write("server/app/a.py")
        code, stderr = self.run_check(FAKE_PYTEST_SLEEP="30", HOOK_PYTEST_TIMEOUT="1")
        self.assertEqual(code, 2)
        self.assertIn("did not finish in time", stderr)
        self.assertNotIn("Traceback", stderr)

    def test_a_reviewer_bash_call_never_triggers_a_check(self):
        self.write("server/app/a.py")
        event = self.bash_event()
        event["agent_type"] = "reviewer"
        code, _ = run_hook("post_bash_check.py", event, self.project, self.env)
        self.assertEqual((code, self.calls()), (0, []))

    def test_malformed_input_is_a_quiet_no_op(self):
        import subprocess as sp, sys
        from hook_helpers import HOOKS_DIR
        for script in ("post_bash_check.py", "post_edit_py.py", "post_edit_ts.py"):
            result = sp.run([sys.executable, str(HOOKS_DIR / script)], input="not json", capture_output=True,
                            text=True, env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.project)})
            self.assertEqual((script, result.returncode, result.stderr), (script, 0, ""))

    def test_interrupted_command_is_not_checked(self):
        self.write("server/app/a.py")
        event = self.bash_event()
        event["tool_response"]["interrupted"] = True
        code, _ = run_hook("post_bash_check.py", event, self.project, self.env)
        self.assertEqual((code, self.calls()), (0, []))


class EditHookSharesTheStateTests(PostBashTestCase):
    def test_a_file_checked_by_the_edit_hook_is_not_checked_again_after_bash(self):
        path = self.write("server/app/a.py")
        edit_event = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Edit",
            "tool_input": {"file_path": str(path)},
            "cwd": str(self.project),
        }
        code, stderr = run_hook("post_edit_py.py", edit_event, self.project, self.env)
        self.assertEqual(code, 0, stderr)
        self.assertIn("pytest", "\n".join(self.calls()))
        self.log.write_text("")
        code, _ = self.run_check()
        self.assertEqual((code, self.calls()), (0, []))

    def test_edit_hook_reports_database_down_in_one_line(self):
        path = self.write("server/app/a.py")
        edit_event = {"tool_name": "Write", "tool_input": {"file_path": str(path)}, "cwd": str(self.project)}
        code, stderr = run_hook(
            "post_edit_py.py", edit_event, self.project,
            {**self.env, "FAKE_PYTEST_CODE": "1", "FAKE_PYTEST_OUT": DB_MESSAGE},
        )
        self.assertEqual(code, 2)
        self.assertIn("docker compose up -d db", stderr)
        self.assertEqual(len(stderr.strip().splitlines()), 1)


class ClientChecksTests(PostBashTestCase):
    def test_changed_ts_file_gets_prettier_and_eslint(self):
        self.write("client/src/a.ts")
        code, stderr = self.run_check()
        self.assertEqual(code, 0, stderr)
        joined = "\n".join(self.calls())
        self.assertIn("prettier --write", joined)
        self.assertIn("eslint --fix", joined)
        self.assertNotIn("pytest", joined)

    def test_eslint_problem_exits_2(self):
        self.write("client/src/a.tsx")
        code, stderr = self.run_check(FAKE_ESLINT_CODE="1", FAKE_ESLINT_OUT="a.tsx 1:1 error no-unused-vars")
        self.assertEqual(code, 2)
        self.assertIn("no-unused-vars", stderr)

    def test_missing_client_dependencies_say_what_to_run(self):
        self.write("client/src/a.ts")
        for name in ("prettier", "eslint"):
            (self.project / "client" / "node_modules" / ".bin" / name).unlink()
        code, stderr = self.run_check()
        self.assertEqual(code, 2)
        self.assertIn("npm install", stderr)


class StateFileTests(PostBashTestCase):
    def test_state_file_is_valid_json_keyed_by_relative_path(self):
        self.write("server/app/a.py")
        self.run_check()
        state = json.loads((self.project / ".claude" / ".hook-state.json").read_text())
        self.assertIn("server/app/a.py", state)

    def test_corrupt_state_file_is_treated_as_empty(self):
        self.write("server/app/a.py")
        (self.project / ".claude" / ".hook-state.json").write_text("{not json")
        code, stderr = self.run_check()
        self.assertEqual(code, 0, stderr)
        self.assertIn("pytest", "\n".join(self.calls()))


if __name__ == "__main__":
    unittest.main()
