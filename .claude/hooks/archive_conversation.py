#!/usr/bin/env python3
"""Archive Claude Code session transcripts into `conversations/` (git-ignored).

Registered in `.claude/settings.json` for `SessionEnd` (exit, `/clear`) and `PreCompact`. Reads the hook
input from stdin, copies the transcript named by `transcript_path` byte for byte to
`conversations/raw/<date>-<session_id>.jsonl`, and renders a readable `conversations/<date>-<session_id>.md`:
the user's messages and Claude's replies in full, one line per tool call, no tool output and no thinking.
Re-running on the same session overwrites both files, so they always hold the whole session.

Other uses:
    python3 archive_conversation.py --backfill          # every transcript of this project
    python3 archive_conversation.py path/to/a.jsonl ... # specific transcripts

Never blocks Claude Code: any error is printed to stderr and the exit code is always 0.
Written for the system Python (3.9+), standard library only.
"""
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

ARCHIVE_DIR = "conversations"
RAW_SUBDIR = "raw"

# Text the harness injects into user turns that the user did not type.
INJECTED_BLOCKS = re.compile(
    r"<(system-reminder|ide_opened_file|ide_selection|local-command-caveat|local-command-stdout)>"
    r".*?</\1>",
    re.DOTALL,
)
COMMAND_NAME = re.compile(r"<command-name>(.*?)</command-name>", re.DOTALL)
COMMAND_ARGS = re.compile(r"<command-args>(.*?)</command-args>", re.DOTALL)
COMMAND_MESSAGE = re.compile(r"<command-message>.*?</command-message>", re.DOTALL)


# --- Locating transcripts ----------------------------------------------------------------------------


def project_dir(event: Optional[dict]) -> Path:
    for candidate in (os.environ.get("CLAUDE_PROJECT_DIR"), (event or {}).get("cwd"), os.getcwd()):
        if candidate:
            return Path(candidate).resolve()
    return Path.cwd()


def project_transcript_dir(project: Path) -> Path:
    """Claude Code stores transcripts in ~/.claude/projects/<cwd with every "/" replaced by "-">/."""
    encoded = str(project).replace("/", "-")
    return Path.home() / ".claude" / "projects" / encoded


# --- Reading the transcript ---------------------------------------------------------------------------


def read_records(transcript: Path) -> List[dict]:
    records = []
    with transcript.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(record)
    return records


def parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def session_date(records: Iterable[dict], transcript: Path) -> str:
    """Local date of the first message, or of the file if the transcript carries no timestamps."""
    for record in records:
        if record.get("type") in ("user", "assistant"):
            stamp = parse_timestamp(record.get("timestamp"))
            if stamp:
                return stamp.astimezone().strftime("%Y-%m-%d")
    return datetime.fromtimestamp(transcript.stat().st_mtime, tz=timezone.utc).astimezone().strftime("%Y-%m-%d")


# --- Rendering ----------------------------------------------------------------------------------------


def clean_user_text(text: str) -> str:
    """Keep what the user typed; show a slash command as `/name args`."""
    text = INJECTED_BLOCKS.sub("", text)
    text = COMMAND_MESSAGE.sub("", text)
    names = COMMAND_NAME.findall(text)
    args = COMMAND_ARGS.findall(text)
    text = COMMAND_NAME.sub("", text)
    text = COMMAND_ARGS.sub("", text)
    if names:
        command = names[0].strip()
        if args and args[0].strip():
            command += " " + args[0].strip()
        text = f"`{command}`\n" + text
    return text.strip()


def user_text(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return clean_user_text(content)
    parts = []
    for block in content or []:
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
        # tool_result blocks are tool output: deliberately omitted from the readable archive.
    return clean_user_text("\n".join(parts))


def describe_tool_call(block: dict) -> str:
    name = block.get("name", "tool")
    args = block.get("input") or {}
    detail = (
        args.get("description")
        or args.get("file_path")
        or args.get("notebook_path")
        or args.get("pattern")
        or args.get("skill")
        or args.get("url")
        or args.get("query")
        or args.get("prompt")
        or args.get("command")
        or ""
    )
    if not isinstance(detail, str):
        detail = json.dumps(detail, ensure_ascii=False)
    detail = " ".join(detail.split())
    if len(detail) > 160:
        detail = detail[:157] + "..."
    return f"- 🔧 **{name}** — {detail}" if detail else f"- 🔧 **{name}**"


def assistant_parts(message: dict) -> List[str]:
    parts = []
    for block in message.get("content") or []:
        kind = block.get("type")
        if kind == "text" and block.get("text", "").strip():
            parts.append(block["text"].strip())
        elif kind == "tool_use":
            parts.append(describe_tool_call(block))
        # thinking blocks are omitted on purpose.
    return parts


def render_markdown(records: List[dict], session_id: str, date: str, event: Optional[dict]) -> str:
    first = next((r for r in records if r.get("type") in ("user", "assistant")), {})
    models = sorted({r["message"].get("model") for r in records if r.get("type") == "assistant"} - {None})
    reason = (event or {}).get("reason") or (event or {}).get("trigger") or ""
    hook_event = (event or {}).get("hook_event_name") or ("backfill" if event is None else "")

    out = [f"# Conversation {date} – `{session_id}`", ""]
    out.append(f"- **Project:** `{first.get('cwd', '')}`")
    out.append(f"- **Branch:** `{first.get('gitBranch', '')}`")
    out.append(f"- **Models:** {', '.join(models) if models else 'unknown'}")
    out.append(f"- **Archived on:** {hook_event}{f' ({reason})' if reason else ''}")
    out.append("")
    out.append("_Tool output and thinking are omitted; the raw JSONL in `raw/` holds everything._")
    out.append("")

    current_turn_id = None
    turn_parts: List[str] = []

    def flush() -> None:
        nonlocal turn_parts, current_turn_id
        if turn_parts:
            out.append("## Claude")
            out.append("")
            out.append("\n\n".join(turn_parts))
            out.append("")
        turn_parts = []
        current_turn_id = None

    for record in records:
        kind = record.get("type")
        if kind not in ("user", "assistant") or record.get("isMeta"):
            continue
        message = record.get("message") or {}
        label = " (subagent)" if record.get("isSidechain") else ""
        if kind == "user":
            text = user_text(message)
            if not text:
                continue
            flush()
            stamp = parse_timestamp(record.get("timestamp"))
            when = f" — {stamp.astimezone().strftime('%H:%M')}" if stamp else ""
            out.append(f"## Yosef{label}{when}")
            out.append("")
            out.append(text)
            out.append("")
        else:
            turn_id = (message.get("id"), bool(record.get("isSidechain")))
            if turn_id != current_turn_id:
                flush()
                current_turn_id = turn_id
            turn_parts.extend(assistant_parts(message))
    flush()
    return "\n".join(out).rstrip() + "\n"


# --- Archiving ----------------------------------------------------------------------------------------


def archive(transcript: Path, project: Path, event: Optional[dict]) -> Path:
    records = read_records(transcript)
    session_id = (event or {}).get("session_id") or transcript.stem
    date = session_date(records, transcript)
    archive_dir = project / ARCHIVE_DIR
    raw_dir = archive_dir / RAW_SUBDIR
    raw_dir.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(transcript, raw_dir / f"{date}-{session_id}.jsonl")
    markdown_path = archive_dir / f"{date}-{session_id}.md"
    markdown_path.write_text(render_markdown(records, session_id, date, event), encoding="utf-8")
    return markdown_path


def main(argv: List[str]) -> None:
    if argv and argv[0] == "--backfill":
        project = project_dir(None)
        transcripts = sorted(project_transcript_dir(project).glob("*.jsonl"))
        if not transcripts:
            print(f"No transcripts found in {project_transcript_dir(project)}", file=sys.stderr)
        for transcript in transcripts:
            print(archive(transcript, project, None))
        return
    if argv:
        project = project_dir(None)
        for transcript in argv:
            print(archive(Path(transcript), project, None))
        return

    event = json.load(sys.stdin)
    transcript = event.get("transcript_path")
    if not transcript or not Path(transcript).is_file():
        print(f"archive_conversation: no transcript at {transcript!r}", file=sys.stderr)
        return
    archive(Path(transcript), project_dir(event), event)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception as error:  # noqa: BLE001 – a hook must never block Claude Code
        print(f"archive_conversation: {type(error).__name__}: {error}", file=sys.stderr)
    sys.exit(0)
