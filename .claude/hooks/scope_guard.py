#!/usr/bin/env python3
"""PreToolUse guard: who may write where, for Edit/Write and for Bash.

One rules table decides, per agent, which paths it may write:

| agent                    | may write                                                         |
|--------------------------|-------------------------------------------------------------------|
| main session, any other  | everything except `server/` and `client/src/` (docs, plans,        |
| agent type               | `.claude/`, README, CI, `client/` config files stay editable)     |
| `backend`                | `server/` and `docs/`                                             |
| `frontend`               | `client/` and `docs/`                                             |
| `qa`                     | `server/tests/`, `server/evals/`, client `*.test/*.spec` files    |
| `reviewer`               | nothing                                                           |

Edit/Write/MultiEdit/NotebookEdit are checked by path. A Bash command is parsed (regex and `shlex`, not a real
shell) for writes: redirects, `tee`, `sed -i`, `perl -i`, `mv`/`cp`/`rsync`/`install`/`ln`/`touch`/`mkdir`/`rm`,
`truncate`, `dd of=`, and inline `python -c` / `python3 -` / `perl -e` / `node -e` scripts that mention a path and
write. Heredoc bodies are data, not commands, unless an interpreter reads them. The parser may over-block; the
message says what to do instead. The pre-commit hook and CI are the backstop for anything it misses.

Escape hatch for the main session: a git-ignored `.claude/main-edits.allow` that only the human creates. While it
exists the guard logs to `.claude/.main-edits.log` instead of blocking the main session.

Exit code 2 plus a reason on stderr blocks the call. Malformed input never blocks.
`write_targets()` is reused by `archive_conversation.py --audit` to count shell writes in old sessions.

Written for the system Python (3.9+), standard library only.
"""
import json
import os
import re
import shlex
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import List, Optional, Tuple

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
MARKER = Path(".claude", "main-edits.allow")
MARKER_LOG = Path(".claude", ".main-edits.log")
GENERATED_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", "node_modules", "dist", ".venv", ".vite"}
CLIENT_TEST_FILE = re.compile(r"^client/.+\.(test|spec)\.tsx?$")

HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
REDIRECT = re.compile(r"^(?:\d*|&)(>>|>\||>)(.*)$")
SUBSTITUTION_SCRIPT = re.compile(r"^[sy]([/|#,!]).*\1.*\1[gpiIe0-9]*$")
WRAPPERS = {"command", "time", "nohup", "env", "exec", "sudo", "nice", "builtin"}
UV_VALUE_OPTIONS = {"--with", "--directory", "--project", "--python", "-p", "--env-file", "--group", "--extra"}
SHELLS = {"bash", "sh", "zsh", "dash"}
ALLOWLISTED = {"git", "ruff", "prettier", "eslint", "alembic", "npx", "npm", "pnpm", "yarn"}

# An inline script is only suspicious if it also looks like it writes.
INLINE_WRITE = re.compile(
    r"write_text|write_bytes|\.write\(|writeFile|appendFile|fs\.(?:write|append|rename|unlink|rm|mkdir|copy)"
    r"|shutil\.|os\.(?:rename|replace|remove|unlink|makedirs|mkdir)|\.unlink\(|\.rename\(|\.touch\(|\.mkdir\("
    r"|open\([^)]*,\s*(?:mode\s*=\s*)?[\"'][rwaxbt+]*[wax+][rwaxbt+]*[\"']"
    r"|\.open\(\s*[\"'][rwaxbt+]*[wax+][rwaxbt+]*[\"']"
    r"|open\([^)]*[\"']\s*>"
)
PATH_IN_SCRIPT = re.compile(r"[\w.~\-/]+")
FILE_EXTENSIONS = (".py", ".ts", ".tsx", ".json", ".toml", ".md", ".css", ".html", ".svg", ".yaml", ".yml",
                   ".ini", ".cfg", ".txt", ".sql", ".js", ".mjs", ".sh")


# --- Rules table ----------------------------------------------------------------------------------------


def under(relative: PurePosixPath, *prefix: str) -> bool:
    parts = relative.parts
    return parts[: len(prefix)] == prefix


def is_generated(relative: PurePosixPath) -> bool:
    return bool(GENERATED_PARTS & set(relative.parts)) or under(relative, "server", "static")


def scope_allows(role: str, relative: PurePosixPath) -> bool:
    """May `role` write `relative` (a path inside the project)?"""
    if role == "reviewer":
        return False
    if is_generated(relative):
        return True
    if role == "backend":
        return under(relative, "server") or under(relative, "docs")
    if role == "frontend":
        return under(relative, "client") or under(relative, "docs")
    if role == "qa":
        return (
            under(relative, "server", "tests")
            or under(relative, "server", "evals")
            or bool(CLIENT_TEST_FILE.match(relative.as_posix()))
        )
    # The main session and every agent type without its own row.
    return not (under(relative, "server") or under(relative, "client", "src"))


def owner_hint(relative: Optional[PurePosixPath]) -> str:
    if relative is not None and under(relative, "client"):
        return "the `frontend` subagent (tests: `qa`)"
    if relative is not None and under(relative, "server"):
        return "the `backend` subagent (tests: `qa`)"
    return "the right subagent"


def explain(role: str, shown: str, relative: Optional[PurePosixPath], via_shell: bool) -> str:
    how = "a shell write into" if via_shell else "an edit of"
    edit_hint = " Source is changed with Edit/Write, not with shell commands." if via_shell else ""
    if role == "reviewer":
        return (
            f"Blocked: {how} {shown}. The reviewer agent is read-only: report the finding with file:line "
            "and let the main session or the owning agent fix it."
        )
    if role == "qa":
        return (
            f"Blocked: {how} {shown}. The qa agent may only write under server/tests/, server/evals/ or "
            "client *.test/*.spec files. Report the needed source change instead."
            + edit_hint
        )
    if role == "backend":
        return (
            f"Blocked: {how} {shown}. The backend agent works in server/ (and docs/). "
            "Client code belongs to the `frontend` subagent; plans and tooling to the main session."
        )
    if role == "frontend":
        return (
            f"Blocked: {how} {shown}. The frontend agent works in client/ (and docs/). "
            "Server code belongs to the `backend` subagent; plans and tooling to the main session."
        )
    return (
        f"Blocked: {how} {shown}. Source under server/ and client/src/ is changed by {owner_hint(relative)}, "
        "not by the main session: delegate, for example \"use the backend subagent to ...\". "
        "The main session edits docs, plans, .claude/, README and CI." + edit_hint
    )


# --- Parsing a Bash command -----------------------------------------------------------------------------


class Segment:
    def __init__(self, text: str) -> None:
        self.text = text
        self.bodies: List[str] = []


def split_segments(command: str) -> List[Segment]:
    """Split a command into simple commands on `;`, `&&`, `||`, `|`, `&`, parentheses and newlines (outside
    quotes), and attach each heredoc body to the segment that opened it."""
    segments: List[Segment] = []
    buffer: List[str] = []
    pending: List[Tuple[str, bool]] = []
    line_segments: List[Segment] = []
    quote: Optional[str] = None
    i, n = 0, len(command)

    def end_segment() -> None:
        text = "".join(buffer).strip()
        buffer.clear()
        if text:
            segment = Segment(text)
            segments.append(segment)
            line_segments.append(segment)

    while i < n:
        char = command[i]
        if quote:
            buffer.append(char)
            if char == "\\" and quote == '"' and i + 1 < n:
                buffer.append(command[i + 1])
                i += 2
                continue
            if char == quote:
                quote = None
            i += 1
            continue
        if char == "\\" and i + 1 < n:
            buffer.append(command[i : i + 2])
            i += 2
            continue
        if char in "'\"":
            quote = char
            buffer.append(char)
            i += 1
            continue
        if command.startswith("<<", i) and not command.startswith("<<<", i):
            match = HEREDOC.match(command, i)
            if match:
                pending.append((match.group(2), match.group(0).startswith("<<-")))
                buffer.append(match.group(0))
                i = match.end()
                continue
        if char == "\n":
            end_segment()
            i += 1
            owners = [s for s in line_segments if "<<" in s.text]
            for index, (delimiter, strip_tabs) in enumerate(pending):
                lines: List[str] = []
                while i < n:
                    newline = command.find("\n", i)
                    line = command[i:] if newline == -1 else command[i:newline]
                    i = n if newline == -1 else newline + 1
                    if (line.strip("\t") if strip_tabs else line) == delimiter:
                        break
                    lines.append(line)
                if index < len(owners):
                    owners[index].bodies.append("\n".join(lines))
            pending.clear()
            line_segments.clear()
            continue
        two = command[i : i + 2]
        if two in ("&&", "||"):
            end_segment()
            i += 2
            continue
        if char in ";()":
            end_segment()
            i += 1
            continue
        if char == "|" and not (buffer and buffer[-1].endswith(">")):
            end_segment()
            i += 1
            continue
        if char == "&":
            previous = buffer[-1][-1:] if buffer else ""
            if previous != ">" and not command.startswith(">", i + 1) and not command.startswith("<", i + 1):
                end_segment()
                i += 1
                continue
        buffer.append(char)
        i += 1
    end_segment()
    return segments


def tokenize(text: str) -> List[str]:
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def positionals(args: List[str], value_options: Tuple[str, ...] = ()) -> List[str]:
    found: List[str] = []
    skip = False
    for arg in args:
        if skip:
            skip = False
            continue
        if arg in value_options:
            skip = True
            continue
        if arg.startswith("-") and arg != "-":
            continue
        if arg:
            found.append(arg)
    return found


def candidate_paths(script: str) -> List[str]:
    paths = []
    for token in PATH_IN_SCRIPT.findall(script):
        if "/" in token or token.endswith(FILE_EXTENSIONS):
            paths.append(token)
    return paths


def resolve(token: str, cwd: Path) -> Optional[Path]:
    if not token or "$" in token or token.startswith(("&", "-")) or token == "/dev/null":
        return None
    path = Path(os.path.expanduser(token))
    if not path.is_absolute():
        path = cwd / path
    return Path(os.path.normpath(str(path)))


def sed_targets(args: List[str]) -> List[str]:
    in_place = any(
        a.startswith("--in-place") or (re.match(r"^-[A-Za-z]*i", a) is not None and not a.startswith("--"))
        for a in args
    )
    if not in_place:
        return []
    has_script_option = any(a in ("-e", "-f", "--expression", "--file") or a.startswith("--expression=") for a in args)
    found = positionals(args, ("-e", "-f", "--expression", "--file"))
    found = [a for a in found if not SUBSTITUTION_SCRIPT.match(a) and not re.search(r"[\s{};$]", a)]
    return found if has_script_option else found[1:] if len(found) > 1 else found


def perl_targets(args: List[str]) -> List[str]:
    in_place = any(
        re.match(r"^-[A-Za-z]*i(\.\w+)?[A-Za-z]*$", a) is not None and not a.startswith(("-M", "-m", "-I"))
        for a in args
    )
    if not in_place:
        return []
    found: List[str] = []
    skip = False
    for arg in args:
        if skip:
            skip = False
            continue
        if re.match(r"^-[A-Za-z]*e$", arg):
            skip = True
            continue
        if arg.startswith("-") or not arg or re.search(r"[\s{};$]", arg):
            continue
        found.append(arg)
    return found


def option_value(args: List[str], names: Tuple[str, ...]) -> Optional[str]:
    for index, arg in enumerate(args):
        if arg in names and index + 1 < len(args):
            return args[index + 1]
        for name in names:
            if name.startswith("--") and arg.startswith(name + "="):
                return arg[len(name) + 1 :]
    return None


def command_targets(name: str, args: List[str]) -> List[str]:
    """Paths the command writes, for the commands whose arguments name them."""
    if name == "tee":
        return positionals(args)
    if name == "sed":
        return sed_targets(args)
    if name == "perl":
        return perl_targets(args)
    if name in ("mv", "touch", "mkdir", "rm", "rmdir"):
        return positionals(args, ("-t", "--target-directory") if name == "mv" else ())
    if name in ("cp", "rsync", "install", "ln"):
        target_dir = option_value(args, ("-t", "--target-directory"))
        if target_dir:
            return [target_dir]
        found = positionals(args, ("-e", "--exclude", "--include", "-m", "-o", "-g"))
        return found[-1:] if len(found) > 1 else []
    if name == "truncate":
        return positionals(args, ("-s", "--size", "-r", "--reference"))
    if name == "dd":
        return [a[3:] for a in args if a.startswith("of=")]
    return []


def inline_script(name: str, args: List[str], bodies: List[str]) -> Optional[str]:
    """The text of an inline interpreter script (`-c`, `-e`, `-` or a heredoc), else None."""
    if re.match(r"^python[0-9.]*$", name):
        flag = option_value(args, ("-c",))
        reads_stdin = "-" in args or (bodies and not [a for a in args if not a.startswith("-")])
        if flag is not None or reads_stdin:
            return "\n".join(([flag] if flag else []) + bodies)
    elif name in ("perl", "ruby", "node"):
        flag = option_value(args, ("-e", "-E", "-p"))
        if flag is not None or bodies:
            return "\n".join(([flag] if flag else []) + bodies)
    return None


def segment_targets(segment: Segment, cwd: Path, depth: int) -> Tuple[List[Path], Path]:
    """Write targets of one simple command; returns them with the (possibly changed) working directory."""
    tokens = tokenize(segment.text)
    targets: List[str] = []
    args: List[str] = []
    skip = False
    for index, token in enumerate(tokens):
        if skip:
            skip = False
            continue
        match = REDIRECT.match(token)
        if match and not token.startswith("<"):
            target = match.group(2)
            if not target and index + 1 < len(tokens):
                target = tokens[index + 1]
                skip = True
            targets.append(target)
            continue
        if token.startswith("<"):
            continue
        args.append(token)

    while args and (ENV_ASSIGNMENT.match(args[0]) or args[0] in WRAPPERS):
        args.pop(0)
    resolved: List[Path] = []
    new_cwd = cwd
    if args:
        name = os.path.basename(args[0])
        rest = args[1:]
        if name == "cd":
            destination = rest[0] if rest and rest[0] != "-" else ""
            path = resolve(destination, cwd) if destination else None
            if path is not None:
                new_cwd = path
        else:
            if name == "uv" and rest[:1] == ["run"]:
                inner = rest[1:]
                while inner and inner[0].startswith("-"):
                    inner = inner[2:] if inner[0] in UV_VALUE_OPTIONS else inner[1:]
                name, rest = (os.path.basename(inner[0]), inner[1:]) if inner else ("uv", [])
            if name in ALLOWLISTED:
                pass
            elif name in SHELLS and depth < 3:
                script = option_value(rest, ("-c",))
                for text in ([script] if script else []) + segment.bodies:
                    resolved.extend(write_targets(text, cwd, depth + 1))
            else:
                targets.extend(command_targets(name, rest))
                script = inline_script(name, rest, segment.bodies)
                if script is not None and INLINE_WRITE.search(script):
                    targets.extend(candidate_paths(script))
    for token in targets:
        path = resolve(token, cwd)
        if path is not None:
            resolved.append(path)
    return resolved, new_cwd


def write_targets(command: str, cwd: Path, depth: int = 0) -> List[Path]:
    """Absolute paths a Bash command appears to write (best effort, regex and shlex based)."""
    found: List[Path] = []
    for segment in split_segments(command):
        paths, cwd = segment_targets(segment, cwd, depth)
        found.extend(paths)
    return found


# --- Hook entry point ------------------------------------------------------------------------------------


def log_main_edit(project: Path, tool: str, shown: str) -> None:
    try:
        with (project / MARKER_LOG).open("a", encoding="utf-8") as handle:
            handle.write(f"{datetime.now().isoformat(timespec='seconds')} {tool} {shown}\n")
    except OSError:
        pass


def relative_to_project(path: Path, project: Path) -> Optional[PurePosixPath]:
    try:
        return PurePosixPath(path.resolve().relative_to(project).as_posix())
    except ValueError:
        return None


def violations(role: str, paths: List[Path], project: Path) -> List[Tuple[str, Optional[PurePosixPath]]]:
    found = []
    for path in paths:
        relative = relative_to_project(path, project)
        if relative is None:
            if role == "reviewer":
                found.append((str(path), None))
            continue
        if not scope_allows(role, relative):
            found.append((relative.as_posix(), relative))
    return found


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".").resolve()
    cwd = Path(event.get("cwd") or project)
    cwd = (cwd if cwd.is_absolute() else project / cwd).resolve()
    role = event.get("agent_type") or "main"

    if tool in EDIT_TOOLS:
        raw = tool_input.get("file_path") or tool_input.get("notebook_path")
        if not raw:
            return
        path = Path(raw)
        paths, via_shell = [path if path.is_absolute() else project / path], False
    elif tool == "Bash":
        command = tool_input.get("command")
        if not isinstance(command, str) or not command.strip():
            return
        paths, via_shell = write_targets(command, cwd), True
    else:
        return

    problems = violations(role, paths, project)
    if not problems:
        return
    if role == "main" and event.get("agent_type") is None and (project / MARKER).exists():
        for shown, _ in problems:
            log_main_edit(project, tool, shown)
        return
    shown, relative = problems[0]
    print(explain(role, shown, relative, via_shell), file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
