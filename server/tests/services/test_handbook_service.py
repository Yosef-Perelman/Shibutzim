"""Handbook splitting, ingestion and similarity search (architecture §6.6, §6.4)."""

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.assistant.llm import EmbedTask, FakeLLM, basis_vector
from app.core.errors import ValidationFailed
from app.models import HandbookChunk
from app.services import handbook_service
from app.services.handbook_service import Section, split_sections

HANDBOOK = Path(__file__).resolve().parents[2] / "handbook" / "employee-handbook.md"

OVERTIME = Section("Overtime", "Hours 9 and 10 are paid at 125%.")
BREAKS = Section("Breaks", "A 30-minute break after 6 hours.")
SWAPS = Section("Shift swaps", "Ask your manager.")


def embeddings_for(*sections: Section) -> dict[str, list[float]]:
    return {
        handbook_service.embedding_text(section): basis_vector(index)
        for index, section in enumerate(sections)
    }


def count_chunks(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(HandbookChunk)) or 0


# --- splitting ---


def test_split_sections_cuts_at_second_level_headings_and_ignores_the_intro():
    markdown = (
        "# Handbook\n\nIntro text.\n\n## Overtime\nPaid more.\n\n## Breaks\nTake one.\nTwice.\n"
    )

    assert split_sections(markdown) == [
        Section("Overtime", "Paid more."),
        Section("Breaks", "Take one.\nTwice."),
    ]


def test_split_sections_keeps_third_level_headings_inside_their_section():
    markdown = "## Pay\nIntro.\n### Tiers\nThree of them.\n"

    assert split_sections(markdown) == [Section("Pay", "Intro.\n### Tiers\nThree of them.")]


def test_split_sections_of_a_document_without_sections_is_empty():
    assert split_sections("# Title only\n\nNo sections.") == []


def test_the_shipped_handbook_has_ten_sections_with_text_and_unique_titles():
    sections = split_sections(HANDBOOK.read_text(encoding="utf-8"))

    titles = [section.title for section in sections]
    assert len(sections) == 10
    assert len(set(titles)) == 10
    assert all(len(section.content) > 100 for section in sections)
    assert {"Overtime", "Shift swaps", "Minimum rest", "Pay day"} <= set(titles)


# --- ingestion ---


def test_ingest_stores_one_chunk_per_section_in_order(session: Session):
    llm = FakeLLM([], embeddings=embeddings_for(OVERTIME, BREAKS))

    stored = handbook_service.ingest_handbook(session, llm, [OVERTIME, BREAKS])

    chunks = list(session.scalars(select(HandbookChunk).order_by(HandbookChunk.position)))
    assert stored == 2
    assert [(c.position, c.section_title, c.content) for c in chunks] == [
        (0, "Overtime", OVERTIME.content),
        (1, "Breaks", BREAKS.content),
    ]


def test_ingest_embeds_all_sections_in_one_provider_call_as_documents(session: Session):
    llm = FakeLLM([], embeddings=embeddings_for(OVERTIME, BREAKS, SWAPS))

    handbook_service.ingest_handbook(session, llm, [OVERTIME, BREAKS, SWAPS])

    assert len(llm.embed_calls) == 1
    texts, task = llm.embed_calls[0]
    assert task is EmbedTask.document
    assert texts[0].startswith("Overtime")


def test_ingest_twice_replaces_the_chunks_instead_of_adding_to_them(session: Session):
    llm = FakeLLM([], embeddings=embeddings_for(OVERTIME, BREAKS))
    handbook_service.ingest_handbook(session, llm, [OVERTIME, BREAKS])
    handbook_service.ingest_handbook(session, llm, [OVERTIME, BREAKS])

    assert count_chunks(session) == 2


def test_ingest_removes_sections_that_left_the_handbook(session: Session):
    llm = FakeLLM([], embeddings=embeddings_for(OVERTIME, BREAKS))
    handbook_service.ingest_handbook(session, llm, [OVERTIME, BREAKS])
    only_breaks = FakeLLM([], embeddings={handbook_service.embedding_text(BREAKS): basis_vector(1)})

    handbook_service.ingest_handbook(session, only_breaks, [BREAKS])

    assert list(session.scalars(select(HandbookChunk.section_title))) == ["Breaks"]


def test_ingest_without_sections_is_rejected_and_keeps_the_old_chunks(session: Session):
    llm = FakeLLM([], embeddings=embeddings_for(OVERTIME))
    handbook_service.ingest_handbook(session, llm, [OVERTIME])

    with pytest.raises(ValidationFailed):
        handbook_service.ingest_handbook(session, llm, [])

    assert count_chunks(session) == 1


# --- search ---


def ingest_three(session: Session) -> FakeLLM:
    embeddings = embeddings_for(OVERTIME, BREAKS, SWAPS)
    embeddings["Can I swap a shift?"] = basis_vector(2)
    embeddings["Mixed question"] = [0.0, 0.6, 0.8] + [0.0] * 765
    llm = FakeLLM([], embeddings=embeddings)
    handbook_service.ingest_handbook(session, llm, [OVERTIME, BREAKS, SWAPS])
    return llm


def test_search_policy_returns_the_closest_section_first_with_its_title(session: Session):
    llm = ingest_three(session)

    matches = handbook_service.search_policy(session, llm, "Can I swap a shift?")

    assert matches[0].section_title == "Shift swaps"
    assert matches[0].content == SWAPS.content
    assert matches[0].score == 1.0


def test_search_policy_ranks_by_cosine_similarity_and_limits_the_count(session: Session):
    llm = ingest_three(session)

    matches = handbook_service.search_policy(session, llm, "Mixed question", limit=2)

    assert [match.section_title for match in matches] == ["Shift swaps", "Breaks"]
    assert [match.score for match in matches] == [0.8, 0.6]


def test_search_policy_embeds_the_question_as_a_query(session: Session):
    llm = ingest_three(session)

    handbook_service.search_policy(session, llm, "Can I swap a shift?")

    assert llm.embed_calls[-1] == (("Can I swap a shift?",), EmbedTask.query)


@pytest.mark.parametrize("query", ["", "   "])
def test_search_policy_rejects_a_blank_question_without_calling_the_provider(
    session: Session, query: str
):
    llm = ingest_three(session)
    calls_before = len(llm.embed_calls)

    with pytest.raises(ValidationFailed):
        handbook_service.search_policy(session, llm, query)

    assert len(llm.embed_calls) == calls_before


def test_search_policy_on_an_empty_handbook_returns_nothing(session: Session):
    llm = FakeLLM([], embeddings={"anything": basis_vector(0)})

    assert handbook_service.search_policy(session, llm, "anything") == []
