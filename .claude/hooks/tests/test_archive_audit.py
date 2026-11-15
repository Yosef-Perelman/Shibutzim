"""Tests for archive_conversation.py: subagent transcripts are archived and listed, and --audit counts Agent
calls and Bash commands that wrote source through the shell."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from typing import List

from hook_helpers import HOOKS_DIR, HookTestCase

import archive_conversation  # noqa: E402  (hook_helpers put the hooks directory on sys.path)

SESSION = "abcdef12-0000-0000-0000-000000000000"


def assistant(*blocks: dict, message_id: str = "m1") -> dict:
    return {
        "type": "assistant",
        "timestamp": "2026-11-12T12:00:00.000Z",
        "cwd": "/p",
        "gitBranch": "plan/x",
        "message": {"id": message_id, "model": "claude-x", "content": list(blocks)},
    }


def tool(name: str, **tool_input) -> dict:
    return {"type": "tool_use", "id": f"toolu_{name}_{abs(hash(json.dumps(tool_input))) % 10000}",
            "name": name, "input": tool_input}


def bash(command: str) -> dict:
    return tool("Bash", command=command)


class AuditTestCase(HookTestCase):
    def write_transcript(self, records: List[dict], name: str = SESSION + ".jsonl") -> Path:
        directory = self.project / "transcripts"
        directory.mkdir(exist_ok=True)
        path = directory / name
        path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
        return path

    def fixture(self) -> Path:
        return self.write_transcript([
            {"type": "user", "timestamp": "2026-11-12T11:59:00.000Z", "message": {"role": "user", "content": "go"}},
            assistant(
                tool("Agent", description="Write tests", subagent_type="qa", prompt="write the tests"),
                bash("cat > server/app/x.py <<'EOF'\nx = 1\nEOF"),
                bash("sed -i '' 's/a/b/' client/src/App.tsx"),
                bash("cd server && uv run pytest -q"),
                bash("echo x > docs/x.md"),
                tool("Edit", file_path="plans/p.md", old_string="a", new_string="b"),
                tool("Write", file_path="plans/q.md", content="x"),
            ),
        ])

    def audit(self, *paths: Path) -> str:
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.project))
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "archive_conversation.py"), "--audit", *map(str, paths)],
            capture_output=True, text=True, env=env, cwd=str(self.project), timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout


class AuditCountTests(AuditTestCase):
    def test_counts_agent_calls_by_type_and_shell_source_writes(self):
        output = self.audit(self.fixture())
        self.assertIn("agent_calls=1", output)
        self.assertIn("qa=1", output)
        self.assertIn("shell_source_writes=2", output)
        self.assertIn("bash=4", output)
        self.assertIn("edit_write=2", output)
        self.assertIn("2026-11-12", output)
        self.assertIn(SESSION[:8], output)

    def test_a_session_without_agent_calls_says_none(self):
        path = self.write_transcript([assistant(bash("ls"))])
        output = self.audit(path)
        self.assertIn("agent_calls=0", output)
        self.assertIn("shell_source_writes=0", output)

    def test_task_tool_name_counts_as_an_agent_call(self):
        path = self.write_transcript([assistant(tool("Task", subagent_type="backend", description="d", prompt="p"))])
        self.assertIn("backend=1", self.audit(path))

    def test_subagent_transcript_records_are_not_double_counted(self):
        sidechain = assistant(bash("echo x > server/app/y.py"))
        sidechain["isSidechain"] = True
        path = self.write_transcript([assistant(bash("ls")), sidechain])
        self.assertIn("shell_source_writes=0", self.audit(path))

    def test_totals_line_sums_several_sessions(self):
        first = self.fixture()
        second = self.write_transcript([assistant(bash("echo x > server/app/z.py"))], name="11111111-x.jsonl")
        output = self.audit(first, second)
        self.assertIn("total", output)
        self.assertIn("shell_source_writes=3", output.splitlines()[-1])


class ArchiveSubagentTests(AuditTestCase):
    def make_session_with_subagent(self) -> Path:
        transcript = self.fixture()
        subagents = transcript.with_suffix("") / "subagents"
        subagents.mkdir(parents=True)
        (subagents / "agent-a1.jsonl").write_text('{"type":"user","message":{"role":"user","content":"hi"}}\n')
        (subagents / "agent-a1.meta.json").write_text(json.dumps({
            "agentType": "qa", "description": "Write tests", "pickedEffortModel": "claude-sonnet-5-5",
            "finished": True,
        }))
        return transcript

    def test_subagent_files_are_copied_next_to_the_raw_transcript(self):
        transcript = self.make_session_with_subagent()
        archive_conversation.archive(transcript, self.project, None)
        target = self.project / "conversations" / "raw" / f"2026-11-12-{SESSION}" / "subagents"
        self.assertTrue((target / "agent-a1.jsonl").is_file())
        self.assertTrue((target / "agent-a1.meta.json").is_file())

    def test_markdown_lists_the_subagents_invoked(self):
        transcript = self.make_session_with_subagent()
        markdown = archive_conversation.archive(transcript, self.project, None).read_text(encoding="utf-8")
        self.assertIn("Subagents invoked", markdown)
        self.assertIn("qa", markdown)
        self.assertIn("Write tests", markdown)

    def test_markdown_says_none_when_no_subagent_was_used(self):
        transcript = self.write_transcript([assistant(bash("ls"))])
        markdown = archive_conversation.archive(transcript, self.project, None).read_text(encoding="utf-8")
        self.assertIn("Subagents invoked", markdown)
        self.assertIn("none", markdown.lower())

    def test_archive_without_a_subagents_directory_still_works(self):
        transcript = self.fixture()
        archive_conversation.archive(transcript, self.project, None)
        self.assertTrue((self.project / "conversations" / "raw" / f"2026-11-12-{SESSION}.jsonl").is_file())


if __name__ == "__main__":
    unittest.main()
