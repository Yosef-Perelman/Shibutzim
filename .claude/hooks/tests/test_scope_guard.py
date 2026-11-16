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

    def test_shell_variable_set_earlier_in_the_command_is_expanded(self):
        root = str(self.project)
        self.assertBlocked(self.bash(f'S={root}/server && cat > "$S/app/x.py" <<\'EOF\'\nx\nEOF'))
        self.assertBlocked(self.bash(f"A={root}/server/app; sed -i '' 's/a/b/' ${{A}}/x.py"))
        self.assertAllowed(self.bash(f'D={root}/docs && echo x > "$D/x.md"'))

    def test_inline_python_that_gets_its_target_as_an_argument_is_blocked(self):
        root = str(self.project)
        script = f"python3 - {root}/server/app <<'EOF'\nimport sys\nopen(sys.argv[1] + '/x.py', 'w').write('x')\nEOF"
        self.assertBlocked(self.bash(script))

    def test_inline_python_with_a_relative_path_uses_the_working_directory(self):
        script = "python3 - <<'EOF'\nfrom pathlib import Path\nPath('tests/x.py').write_text('x')\nEOF"
        self.assertBlocked(self.bash(script, cwd=str(self.project / "server")))

    def test_bash_c_and_bash_heredoc_are_looked_into(self):
        self.assertBlocked(self.bash("bash -c 'echo x > server/app/x.py'"))
        self.assertBlocked(self.bash("bash <<'EOF'\necho x > server/app/x.py\nEOF"))

    def test_sed_with_several_files_checks_every_file(self):
        self.assertBlocked(self.bash("sed -i '' 's/a/b/' server/app/x.py README.md"))
        self.assertBlocked(self.bash("sed -i '' 's/a/b/' README.md server/app/x.py"))
        self.assertAllowed(self.bash("sed -i '' 's/a/b/' README.md AGENTS.md"))

    def test_script_piped_into_an_interpreter_is_looked_into(self):
        self.assertBlocked(self.bash("cat <<'EOF' | python3 -\nopen('server/app/x.py','w').write('x')\nEOF"))
        self.assertBlocked(self.bash("echo \"open('server/app/x.py','w').write('x')\" | python3"))
        self.assertBlocked(self.bash("cat <<EOF | bash\necho x > server/app/x.py\nEOF"))
        self.assertAllowed(self.bash("cat <<'EOF' | python3 -\nprint(1)\nEOF"))

    def test_xargs_find_exec_and_timeout_are_unwrapped(self):
        for command in (
            "find server -name '*.py' -exec sed -i '' 's/a/b/' {} +",
            "find client/src -name '*.ts' -exec tee {} \\;",
            "find server -name '*.orig' -delete",
            "git ls-files server | xargs sed -i '' 's/a/b/'",
            "ls server/app | xargs -n1 rm",
            "timeout 5 tee server/app/x.py",
            "timeout -s KILL 5 sh -c 'echo x > server/app/x.py'",
        ):
            with self.subTest(command=command):
                self.assertBlocked(self.bash(command))
        self.assertAllowed(self.bash("find server -name '*.py' -exec grep foo {} +"))
        self.assertAllowed(self.bash("ls server | xargs grep foo"))
        self.assertAllowed(self.bash("timeout 5 uv run pytest -q"))

    def test_redirect_stuck_to_a_word_is_detected(self):
        self.assertBlocked(self.bash("echo x>server/app/x.py"))
        self.assertBlocked(self.bash("echo x>>client/src/a.ts"))
        self.assertAllowed(self.bash("cd server && ls app 2>/dev/null"))
        self.assertAllowed(self.bash("uv run pytest -q 2>&1 | tail -3"))

    def test_stderr_redirect_does_not_turn_into_a_path(self):
        self.assertAllowed(self.bash("sed -n 1,5p app/x.py 2>/dev/null", cwd=str(self.project / "server")))

    def test_paths_that_differ_only_in_case_are_the_same_path(self):
        self.assertBlocked(self.bash("echo x > SERVER/app/x.py"))
        self.assertBlocked(self.bash("echo x > Client/Src/a.ts"))

    def test_the_escape_hatch_file_cannot_be_written_by_the_main_session(self):
        self.assertBlocked(self.bash("touch .claude/main-edits.allow"), "escape hatch")
        self.assertBlocked(self.bash("echo x > .claude/main-edits.allow"))

    def test_only_caches_and_build_output_are_exempt(self):
        self.assertAllowed(self.bash("echo x > client/dist/index.html"))
        self.assertAllowed(self.bash("echo x > server/static/index.html"))
        self.assertBlocked(self.bash("echo x > client/src/dist/x.ts"))

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

    def test_nobody_may_write_the_escape_hatch_by_edit_even_with_it_present(self):
        for agent in (None, "backend", "general-purpose"):
            with self.subTest(agent=agent):
                self.assertBlocked(self.edit(".claude/main-edits.allow", agent=agent, tool="Write"), "escape hatch")
        (self.project / ".claude" / "main-edits.allow").write_text("")
        self.assertBlocked(self.edit(".claude/main-edits.allow", tool="Write"))

    def test_paths_in_a_different_case_are_the_same_path(self):
        self.assertBlocked(self.edit("Server/app/main.py"))
        self.assertBlocked(self.edit("CLIENT/SRC/App.tsx", tool="Write"))

    def test_a_git_worktree_inside_the_project_is_treated_as_the_project(self):
        self.assertBlocked(self.edit(".claude/worktrees/w1/server/app/x.py"))
        self.assertAllowed(self.edit(".claude/worktrees/w1/server/app/x.py", agent="backend"))
        self.assertAllowed(self.edit(".claude/worktrees/w1/docs/x.md"))

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
        self.assertAllowed(self.edit("docs/glossary.md", agent="frontend"))
        self.assertAllowed(self.edit("design/design-system.md", agent="frontend"))
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


if __name__ == "__main__":
    unittest.main()
