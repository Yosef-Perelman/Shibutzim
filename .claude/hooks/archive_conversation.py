#!/usr/bin/env python3
"""Archive Claude Code session transcripts into `conversations/` (git-ignored).

Registered in `.claude/settings.json` for `SessionEnd` (exit, `/clear`) and `PreCompact`. Reads the hook
input from stdin, copies the transcript named by `transcript_path` byte for byte to
`conversations/raw/<date>-<session_id>.jsonl`, and renders a readable `conversations/<date>-<session_id>.md`:
the user's messages and Claude's replies in full, one line per tool call, no tool output and no thinking.
Re-running on the same session overwrites both files, so they always hold the whole session.

Subagent transcripts (`<session>/subagents/agent-*.jsonl` and `.meta.json`, next to the main transcript) are
copied to `conversations/raw/<date>-<session_id>/subagents/`, and the Markdown lists the subagents invoked.

Other uses:
    python3 archive_conversation.py --backfill          # every transcript of this project
    python3 archive_conversation.py path/to/a.jsonl ... # specific transcripts
    python3 archive_conversation.py --audit [a.jsonl ...]  # per session: Agent calls by type, and Bash commands
                                                           # that wrote source through the shell (default: all)

Never blocks Claude Code: any error is printed to stderr and the exit code is always 0.
Written for the system Python (3.9+), standard library only.
"""
import json
import os
import re
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

ARCHIVE_DIR = "conversations"
RAW_SUBDIR = "raw"
SUBAGENTS_SUBDIR = "subagents"
AGENT_TOOLS = {"Agent", "Task"}
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

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
    if name in AGENT_TOOLS and args.get("subagent_type"):
        name = f"{name} ({args['subagent_type']})"
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


def tool_blocks(records: Iterable[dict]) -> Iterable[dict]:
    """Every `tool_use` block of the main conversation (not of subagent sidechains), once per tool-use id."""
    seen = set()
    for record in records:
        if record.get("type") != "assistant" or record.get("isSidechain"):
            continue
        for block in (record.get("message") or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("id") not in seen:
                seen.add(block.get("id"))
                yield block


def agent_calls(records: Iterable[dict]) -> List[dict]:
    """The `Agent` (formerly `Task`) tool calls of the main conversation."""
    return [block for block in tool_blocks(records) if block.get("name") in AGENT_TOOLS]


def read_subagent_meta(subagents_dir: Path) -> Dict[str, dict]:
    """`agent-*.meta.json` files keyed by the id of the `tool_use` that spawned the subagent."""
    found: Dict[str, dict] = {}
    for meta_file in sorted(subagents_dir.glob("*.meta.json")):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(meta, dict) and meta.get("toolUseId"):
            found[meta["toolUseId"]] = meta
    return found


def render_subagents(records: List[dict], meta_by_call: Dict[str, dict]) -> List[str]:
    lines = ["## Subagents invoked", ""]
    calls = agent_calls(records)
    if not calls:
        return lines + ["- none", ""]
    for call in calls:
        args = call.get("input") or {}
        kind = args.get("subagent_type") or "general-purpose"
        description = " ".join(str(args.get("description") or "").split())
        model = (meta_by_call.get(call.get("id")) or {}).get("pickedEffortModel")
        lines.append(f"- **{kind}**" + (f" — {description}" if description else "") + (f" ({model})" if model else ""))
    return lines + [""]


def render_markdown(
    records: List[dict],
    session_id: str,
    date: str,
    event: Optional[dict],
    meta_by_call: Optional[Dict[str, dict]] = None,
) -> str:
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
    out.extend(render_subagents(records, meta_by_call or {}))
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
    source_subagents = transcript.with_suffix("") / SUBAGENTS_SUBDIR
    meta_by_call: Dict[str, dict] = {}
    if source_subagents.is_dir():
        shutil.copytree(source_subagents, raw_dir / f"{date}-{session_id}" / SUBAGENTS_SUBDIR, dirs_exist_ok=True)
        meta_by_call = read_subagent_meta(source_subagents)
    markdown_path = archive_dir / f"{date}-{session_id}.md"
    markdown_path.write_text(render_markdown(records, session_id, date, event, meta_by_call), encoding="utf-8")
    return markdown_path


# --- Audit: was the work delegated, and did anything write source through the shell? -------------------


def shell_source_writes(records: List[dict], project: Path) -> int:
    """Bash commands of the main conversation that wrote under `server/` or `client/src/` (see scope_guard.py)."""
    import scope_guard

    cwd_of = {}
    for record in records:
        if record.get("type") == "assistant" and record.get("cwd"):
            for block in (record.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    cwd_of[block.get("id")] = record["cwd"]

    count = 0
    for block in tool_blocks(records):
        command = (block.get("input") or {}).get("command")
        if block.get("name") != "Bash" or not isinstance(command, str):
            continue
        cwd = Path(cwd_of.get(block.get("id")) or project)
        try:
            cwd.resolve().relative_to(project)
        except ValueError:
            cwd = project
        for target in scope_guard.write_targets(command, cwd.resolve()):
            relative = scope_guard.relative_to_project(target, project)
            if relative is None or scope_guard.is_generated(relative):
                continue
            if not scope_guard.scope_allows("main", relative):  # server/ and client/src/
                count += 1
                break
    return count


def audit_session(transcript: Path, project: Path) -> Tuple[str, Counter, Counter]:
    records = read_records(transcript)
    blocks = list(tool_blocks(records))
    names = Counter(block.get("name") for block in blocks)
    types = Counter(
        (block.get("input") or {}).get("subagent_type") or "general-purpose"
        for block in blocks
        if block.get("name") in AGENT_TOOLS
    )
    counts = Counter(
        agent_calls=sum(types.values()),
        bash=names["Bash"],
        edit_write=sum(names[name] for name in EDIT_TOOLS),
        shell_source_writes=shell_source_writes(records, project),
    )
    session = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", transcript.stem)  # archived copies are named <date>-<session>
    return f"{session_date(records, transcript)} {session[:8]}", counts, types


def format_audit_line(label: str, counts: Counter, types: Counter) -> str:
    kinds = ", ".join(f"{kind}={number}" for kind, number in sorted(types.items()))
    calls = f"agent_calls={counts['agent_calls']}" + (f" ({kinds})" if kinds else "")
    return (
        f"{label}  {calls}  bash={counts['bash']}  edit_write={counts['edit_write']}"
        f"  shell_source_writes={counts['shell_source_writes']}"
    )


def audit(transcripts: List[Path], project: Path) -> List[str]:
    rows = sorted((audit_session(path, project) for path in transcripts), key=lambda row: row[0])
    lines = [format_audit_line(label, counts, types) for label, counts, types in rows]
    if len(rows) > 1:
        total, total_types = Counter(), Counter()
        for _, counts, types in rows:
            total.update(counts)
            total_types.update(types)
        lines.append(format_audit_line("total        ", total, total_types))
    return lines


def main(argv: List[str]) -> None:
    if argv and argv[0] == "--audit":
        project = project_dir(None)
        transcripts = [Path(a) for a in argv[1:]] or sorted(project_transcript_dir(project).glob("*.jsonl"))
        print("\n".join(audit(transcripts, project)))
        return
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
