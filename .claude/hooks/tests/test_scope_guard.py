"""Tests for scope_guard.py: one rules table for every agent, applied to Edit/Write and to Bash."""
import unittest
from typing import Optional

from hook_helpers import HookTestCase, run_hook


class ScopeGuardTestCase(HookTestCase):
    def bash(self, command: str, agent: Optional[str] = None, cwd: Optional[str] = None):
        event = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "cwd": cwd or str(self.project),
        }
        if agent:
            event["agent_type"] = agent
        return run_hook("scope_guard.py", event, self.project)

    def edit(self, path: str, agent: Optional[str] = None, tool: str = "Edit"):
        event = {
            "hook_event_name": "PreToolUse",
            "tool_name": tool,
            "tool_input": {"file_path": path},
            "cwd": str(self.project),
        }
        if agent:
            event["agent_type"] = agent
        return run_hook("scope_guard.py", event, self.project)

    def assertBlocked(self, result, *words: str) -> None:
        code, stderr = result
        self.assertEqual(code, 2, f"expected a block, got exit {code}: {stderr!r}")
        for word in words:
            self.assertIn(word, stderr)

    def assertAllowed(self, result) -> None:
        code, stderr = result
        self.assertEqual(code, 0, f"expected allowed, got exit {code}: {stderr!r}")


class MainSessionShellTests(ScopeGuardTestCase):
    def test_heredoc_into_server_is_blocked_and_says_use_edit_write(self):
        result = self.bash("cat > server/app/x.py <<'EOF'\nx = 1\nEOF")
        self.assertBlocked(result, "Edit/Write", "backend")

    def test_heredoc_into_client_src_is_blocked_and_names_frontend(self):
        self.assertBlocked(self.bash("cat > client/src/App.tsx <<'EOF'\nx\nEOF"), "frontend")

    def test_inline_python_that_writes_client_source_is_blocked(self):
        script = "python3 - <<EOF\nfrom pathlib import Path\nPath('client/src/App.tsx').write_text('x')\nEOF"
        self.assertBlocked(self.bash(script), "Edit/Write")

    def test_inline_python_c_that_writes_server_source_is_blocked(self):
        self.assertBlocked(self.bash("python3 -c \"open('server/app/x.py','w').write('x')\""))

    def test_inline_python_that_only_reads_source_is_allowed(self):
        script = "python3 - <<EOF\nprint(open('client/src/App.tsx').read())\nEOF"
        self.assertAllowed(self.bash(script))

    def test_redirects_append_and_tee_are_blocked(self):
        self.assertBlocked(self.bash("echo x >> server/app/x.py"))
        self.assertBlocked(self.bash("echo x | tee -a server/app/x.py"))
        self.assertBlocked(self.bash("echo x &> client/src/a.ts"))

    def test_sed_and_perl_in_place_are_blocked(self):
        self.assertBlocked(self.bash("sed -i '' 's/a/b/' server/app/x.py"))
        self.assertBlocked(self.bash("sed -i.bak -e 's/a/b/' client/src/App.tsx"))
        self.assertBlocked(self.bash("perl -pi -e 's/a/b/' client/src/App.tsx"))

    def test_move_copy_and_friends_into_source_are_blocked(self):
        for command in (
            "mv a.py server/app/b.py",
            "cp a.ts client/src/b.ts",
            "rsync -a staging/ server/app/",
            "install -m 644 a.py server/app/a.py",
            "truncate -s 0 server/app/x.py",
            "dd if=a of=server/app/x.py",
        ):
            with self.subTest(command=command):
                self.assertBlocked(self.bash(command))

    def test_relative_path_after_cd_is_resolved(self):
        self.assertBlocked(self.bash("cd server && echo x > app/y.py"))
        self.assertAllowed(self.bash("cd docs && echo x > y.md"))

    def test_relative_path_from_a_source_cwd_is_resolved(self):
        self.assertBlocked(self.bash("echo x > app/y.py", cwd=str(self.project / "server")))

    def test_allowlisted_and_harmless_commands_run(self):
        for command in (
            "uv run ruff format .",
            "cd server && uv run ruff format .",
            "cd server && uv run ruff check --fix .",
            "cd server && uv run alembic revision --autogenerate --rev-id 0009 -m x",
            "git restore server/app/x.py",
            "git checkout -- client/src/App.tsx",
            "cd client && npx prettier --write src/App.tsx",
            "cd client && npm run format",
            "cd server && uv run pytest -q 2>&1 | tail -5",
            "echo x > /dev/null",
            "cat server/app/x.py > /tmp/copy.py",
            "ls server && grep -rn foo client/src",
        ):
            with self.subTest(command=command):
                self.assertAllowed(self.bash(command))

    def test_docs_plans_claude_readme_and_client_config_stay_writable(self):
        for command in (
            "echo x > docs/x.md",
            "echo x > plans/x.md",
            "echo x > .claude/hooks/x.py",
            "echo x > README.md",
            "echo x > client/vite.config.ts",
            "cat > docs/x.md <<'EOF'\nsee server/app/x.py and client/src/App.tsx\nEOF",
        ):
            with self.subTest(command=command):
                self.assertAllowed(self.bash(command))

    def test_generated_directories_inside_source_are_ignored(self):
        self.assertAllowed(self.bash("rm server/app/__pycache__/x.pyc"))
        self.assertAllowed(self.bash("echo x > client/node_modules/.cache/y"))

    def test_other_agent_types_are_treated_like_main(self):
        self.assertBlocked(self.bash("echo x > server/app/x.py", agent="general-purpose"))
        self.assertBlocked(self.edit("server/app/x.py", agent="Explore"))

    def test_malformed_input_never_blocks(self):
        code, _ = run_hook("scope_guard.py", {"tool_name": "Bash", "tool_input": {}}, self.project)
        self.assertEqual(code, 0)


class MainSessionEditTests(ScopeGuardTestCase):
    def test_edit_of_server_source_is_blocked_and_names_backend(self):
        self.assertBlocked(self.edit(str(self.project / "server/app/main.py")), "backend")

    def test_write_of_client_source_is_blocked_and_names_frontend(self):
        self.assertBlocked(self.edit(str(self.project / "client/src/App.tsx"), tool="Write"), "frontend")

    def test_relative_path_is_resolved_against_the_project(self):
        self.assertBlocked(self.edit("server/app/main.py"))

    def test_docs_plans_claude_and_readme_are_allowed(self):
        for path in ("docs/glossary.md", "plans/ROADMAP.md", ".claude/hooks/x.py", "README.md", "AGENTS.md"):
            with self.subTest(path=path):
                self.assertAllowed(self.edit(path))

    def test_client_config_files_are_allowed(self):
        self.assertAllowed(self.edit("client/package.json"))
        self.assertAllowed(self.edit("client/vite.config.ts"))

    def test_paths_outside_the_project_are_allowed(self):
        self.assertAllowed(self.edit("/tmp/scratch/x.py"))

    def test_marker_file_lets_the_main_session_edit_source(self):
        (self.project / ".claude" / "main-edits.allow").write_text("")
        self.assertAllowed(self.edit("server/app/main.py"))
        self.assertAllowed(self.bash("echo x > server/app/x.py"))
        self.assertTrue((self.project / ".claude" / ".main-edits.log").exists())

    def test_marker_file_does_not_widen_a_subagent(self):
        (self.project / ".claude" / "main-edits.allow").write_text("")
        self.assertBlocked(self.edit("server/app/main.py", agent="qa"))


class BackendFrontendTests(ScopeGuardTestCase):
    def test_backend_may_write_server_by_edit_and_by_shell(self):
        self.assertAllowed(self.edit("server/app/x.py", agent="backend"))
        self.assertAllowed(self.bash("cat > server/app/x.py <<'EOF'\nx = 1\nEOF", agent="backend"))

    def test_backend_may_update_docs_but_not_client_or_plans(self):
        self.assertAllowed(self.edit("docs/glossary.md", agent="backend"))
        self.assertBlocked(self.edit("client/src/App.tsx", agent="backend"), "frontend")
        self.assertBlocked(self.edit("plans/ROADMAP.md", agent="backend"))
        self.assertBlocked(self.bash("echo x > client/src/a.ts", agent="backend"))

    def test_frontend_may_write_client_but_not_server(self):
        self.assertAllowed(self.edit("client/src/App.tsx", agent="frontend"))
        self.assertAllowed(self.edit("client/package.json", agent="frontend"))
        self.assertAllowed(self.edit("docs/design-system.md", agent="frontend"))
        self.assertBlocked(self.edit("server/app/x.py", agent="frontend"), "backend")
        self.assertBlocked(self.bash("echo x > server/app/x.py", agent="frontend"))


class QaTests(ScopeGuardTestCase):
    def test_qa_may_write_server_tests_and_evals(self):
        self.assertAllowed(self.edit("server/tests/unit/test_x.py", agent="qa"))
        self.assertAllowed(self.edit("server/evals/case.py", agent="qa"))
        self.assertAllowed(self.bash("tee server/tests/x.py < /dev/null", agent="qa"))

    def test_qa_may_write_client_test_and_spec_files(self):
        self.assertAllowed(self.edit("client/src/a.test.tsx", agent="qa"))
        self.assertAllowed(self.edit("client/src/b.spec.ts", agent="qa"))

    def test_qa_cannot_write_source_by_edit_or_shell(self):
        self.assertBlocked(self.edit("server/app/x.py", agent="qa"), "qa")
        self.assertBlocked(self.bash("echo x | tee server/app/x.py", agent="qa"))
        self.assertBlocked(self.bash("echo x | tee -a server/app/main.py", agent="qa"))
        self.assertBlocked(self.edit("client/src/a.tsx", agent="qa"))

    def test_qa_cannot_write_docs_or_plans(self):
        self.assertBlocked(self.edit("docs/x.md", agent="qa"))
        self.assertBlocked(self.bash("echo x > plans/x.md", agent="qa"))


class ReviewerTests(ScopeGuardTestCase):
    def test_reviewer_cannot_edit_anything(self):
        self.assertBlocked(self.edit("docs/x.md", agent="reviewer"), "reviewer")
        self.assertBlocked(self.edit("server/tests/x.py", agent="reviewer", tool="Write"))

    def test_reviewer_cannot_write_by_shell(self):
        self.assertBlocked(self.bash("echo x >> docs/x.md", agent="reviewer"))
        self.assertBlocked(self.bash("echo x > /tmp/x", agent="reviewer"))

    def test_reviewer_may_run_read_only_commands(self):
        self.assertAllowed(self.bash("git diff main...HEAD", agent="reviewer"))
        self.assertAllowed(self.bash("git log --oneline | head -5", agent="reviewer"))


if __name__ == "__main__":
    unittest.main()
