"""Tests for reviewer_bash_guard.py: the reviewer's Bash is limited to read-only git commands."""
import unittest

from hook_helpers import HookTestCase, run_hook


class ReviewerBashGuardTests(HookTestCase):
    def run_command(self, command: str):
        event = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}}
        return run_hook("reviewer_bash_guard.py", event, self.project)

    def test_read_only_git_commands_are_allowed(self):
        for command in (
            "git diff main...HEAD",
            "git diff main...HEAD --stat",
            "git diff main...HEAD -- server/app/services",
            "git log --oneline main..HEAD",
            'git log --format="%h %s" -n 20',
            "git show HEAD~1:plans/ROADMAP.md",
            "git status --short",
            "git ls-files server/app",
            "git blame -L 1,20 server/app/main.py",
            "git rev-parse --abbrev-ref HEAD",
            "git merge-base main HEAD",
            'git log --format="%C(auto)%h %s"',
        ):
            with self.subTest(command=command):
                code, stderr = self.run_command(command)
                self.assertEqual(code, 0, stderr)

    def test_git_commands_that_change_things_are_blocked(self):
        for command in ("git push", "git commit -m x", "git checkout main", "git reset --hard", "git add -A",
                        "git switch main", "git merge main", "git restore ."):
            with self.subTest(command=command):
                code, stderr = self.run_command(command)
                self.assertEqual(code, 2)
                self.assertIn("read-only", stderr)

    def test_other_commands_are_blocked(self):
        for command in ("ls", "cat server/app/main.py", "uv run pytest -q", "python3 -c 'print(1)'", "rm x", ""):
            with self.subTest(command=command):
                code, _ = self.run_command(command)
                self.assertEqual(code, 2)

    def test_chaining_redirects_and_substitution_are_blocked(self):
        for command in (
            "git diff main > out.txt",
            "git diff main >> out.txt",
            "git diff main && rm x",
            "git diff main; rm x",
            "git diff main | tee x",
            "git diff $(rm x)",
            "git diff `rm x`",
            "git status\nrm x",
            "git diff main &",
        ):
            with self.subTest(command=command):
                code, _ = self.run_command(command)
                self.assertEqual(code, 2)

    def test_options_that_write_or_run_programs_are_blocked(self):
        for command in (
            "git diff --output=out.txt main",
            "git diff --output out.txt main",
            "git diff --no-index /dev/null .env",
            "git diff --ext-diff main",
            "git -c core.pager=sh diff",
            "git --no-pager diff",
        ):
            with self.subTest(command=command):
                code, _ = self.run_command(command)
                self.assertEqual(code, 2)

    def test_non_bash_events_are_ignored(self):
        event = {"tool_name": "Read", "tool_input": {"file_path": "x"}}
        code, _ = run_hook("reviewer_bash_guard.py", event, self.project)
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
