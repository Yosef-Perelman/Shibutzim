"""Prompts live in files next to this module, never in Python strings (coding-rules).

Reviewing a prompt change is reviewing a markdown diff.
"""

from functools import cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent


@cache
def load_prompt(name: str) -> str:
    """The text of `prompts/<name>`; `name` may not point outside the prompts folder."""
    path = (PROMPTS_DIR / name).resolve()
    if not path.is_relative_to(PROMPTS_DIR):
        raise ValueError(f"prompt {name!r} is outside the prompts folder")
    return path.read_text(encoding="utf-8").strip()
