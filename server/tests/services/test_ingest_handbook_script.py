"""scripts/ingest_handbook.py reads every handbook/*.md file and replaces the stored chunks."""

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.assistant.llm import FakeLLM, basis_vector
from app.models import HandbookChunk
from app.services import handbook_service
from app.services.handbook_service import Section
from scripts import ingest_handbook


def test_ingest_reads_every_markdown_file_in_name_order(session: Session, tmp_path: Path):
    (tmp_path / "b-extra.md").write_text("## Lateness\nBe on time.\n", encoding="utf-8")
    (tmp_path / "a-main.md").write_text("# Title\n## Overtime\nPaid more.\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("## Ignored\nNot markdown.\n", encoding="utf-8")
    sections = [Section("Overtime", "Paid more."), Section("Lateness", "Be on time.")]
    llm = FakeLLM(
        [],
        embeddings={
            handbook_service.embedding_text(section): basis_vector(index)
            for index, section in enumerate(sections)
        },
    )

    stored = ingest_handbook.ingest(session, llm, tmp_path)

    titles = list(
        session.scalars(select(HandbookChunk.section_title).order_by(HandbookChunk.position))
    )
    assert stored == 2
    assert titles == ["Overtime", "Lateness"]


def test_ingest_twice_leaves_the_same_number_of_chunks(session: Session, tmp_path: Path):
    (tmp_path / "handbook.md").write_text("## Overtime\nPaid more.\n", encoding="utf-8")
    llm = FakeLLM(
        [],
        embeddings={
            handbook_service.embedding_text(Section("Overtime", "Paid more.")): basis_vector(0)
        },
    )

    ingest_handbook.ingest(session, llm, tmp_path)
    ingest_handbook.ingest(session, llm, tmp_path)

    assert session.scalar(select(func.count()).select_from(HandbookChunk)) == 1
