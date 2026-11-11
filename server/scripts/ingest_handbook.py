"""Ingest the employee handbook: split by `##` section, embed, and replace the stored chunks.

    cd server && uv run python scripts/ingest_handbook.py

Reads every `server/handbook/*.md` in name order. Safe to run again: the chunks are replaced, not
added to. Needs `GEMINI_API_KEY`; the whole handbook is embedded in one provider call.
"""

import sys
from pathlib import Path

# `python scripts/ingest_handbook.py` puts scripts/ on sys.path, not the server root with `app`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session  # noqa: E402

from app.assistant.llm import LLM  # noqa: E402
from app.assistant.llm.provider import get_llm  # noqa: E402
from app.core.errors import DomainError  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.services import handbook_service  # noqa: E402

HANDBOOK_DIR = Path(__file__).resolve().parents[1] / "handbook"


def ingest(session: Session, llm: LLM, directory: Path = HANDBOOK_DIR) -> int:
    """Replace the stored chunks with the sections of every markdown file in `directory`."""
    sections = []
    for path in sorted(directory.glob("*.md")):
        sections += handbook_service.split_sections(path.read_text(encoding="utf-8"))
    return handbook_service.ingest_handbook(session, llm, sections)


def main() -> None:
    try:
        llm = get_llm()
        with SessionLocal() as session:
            stored = ingest(session, llm)
    except DomainError as error:
        sys.exit(f"Could not ingest the handbook: {error.message}")
    print(f"{stored} sections")


if __name__ == "__main__":
    main()
