#!/usr/bin/env python3
"""PreToolUse guard registered only in the reviewer subagent's frontmatter (matcher `Bash`).

The reviewer reads; it never changes anything. Its Bash is limited to one plain read-only git command:
`git diff | log | show | status | ls-files | blame | rev-parse | merge-base`. Pipes, `;`, `&`, redirects, command
substitution and newlines are refused, as are the options that write a file or run a program
(`--output`, `--no-index`, `--ext-diff`, `--textconv`) and anything before the subcommand (`git -c ...`).

Exit code 2 plus a reason on stderr blocks the call. Written for the system Python (3.9+), standard library only.
"""
import json
import re
import shlex
import sys

ALLOWED_SUBCOMMANDS = {"diff", "log", "show", "status", "ls-files", "blame", "rev-parse", "merge-base"}
FORBIDDEN_CHARACTERS = re.compile(r"[;&|<>`$\n\r\\]")
FORBIDDEN_OPTIONS = ("--output", "--no-index", "--ext-diff", "--textconv", "--open-files-in-pager", "--exec-path")


def reason(command: str) -> str:
    """Why the command is refused, or an empty string when it is allowed."""
    if FORBIDDEN_CHARACTERS.search(command):
        return "pipes, chaining, redirects, substitution and newlines are not allowed"
    try:
        tokens = shlex.split(command)
    except ValueError:
        return "the command could not be parsed"
    if len(tokens) < 2 or tokens[0] != "git" or tokens[1] not in ALLOWED_SUBCOMMANDS:
        return "only `git " + "|".join(sorted(ALLOWED_SUBCOMMANDS)) + "` is allowed"
    for token in tokens[2:]:
        if any(token == option or token.startswith(option + "=") for option in FORBIDDEN_OPTIONS):
            return f"the option {token.split('=')[0]} writes a file or runs a program"
    return ""


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return
    if event.get("tool_name") != "Bash":
        return
    command = (event.get("tool_input") or {}).get("command") or ""
    problem = reason(command.strip())
    if problem:
        print(
            f"Blocked: the reviewer agent is read-only and may run only plain git read commands ({problem}). "
            "Read files with Read, Grep and Glob, and report what you find.",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
