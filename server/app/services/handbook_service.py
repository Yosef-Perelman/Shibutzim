"""The employee handbook: splitting it into sections, ingesting it and searching it (§6.4, §6.6).

Every signed-in user may read the handbook, so there is nothing to authorize here.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.assistant.llm import LLM, EmbedTask
from app.core.errors import ErrorCode, ValidationFailed
from app.models import HandbookChunk
from app.repositories import handbook_repository

SECTION_PREFIX = "## "
DEFAULT_MATCHES = 3
SCORE_DECIMALS = 4


@dataclass(frozen=True)
class Section:
    title: str
    content: str


@dataclass(frozen=True)
class PolicyMatch:
    """A handbook section close to a question; `score` is the cosine similarity (1 = identical)."""

    section_title: str
    content: str
    score: float


def split_sections(markdown: str) -> list[Section]:
    """Cut at `## ` headings. Text before the first one (the title and intro) is not a section."""
    sections: list[Section] = []
    title: str | None = None
    body: list[str] = []
    for line in markdown.splitlines():
        if line.startswith(SECTION_PREFIX):
            if title is not None:
                sections.append(Section(title, "\n".join(body).strip()))
            title, body = line.removeprefix(SECTION_PREFIX).strip(), []
        elif title is not None:
            body.append(line)
    if title is not None:
        sections.append(Section(title, "\n".join(body).strip()))
    return sections


def embedding_text(section: Section) -> str:
    """The title is part of what is embedded, so a question that names the topic finds it."""
    return f"{section.title}\n{section.content}"


def ingest_handbook(session: Session, llm: LLM, sections: Sequence[Section]) -> int:
    """Replace the stored chunks with `sections`, embedding them in one provider call."""
    if not sections:
        raise ValidationFailed(
            ErrorCode.validation_error, "The handbook has no sections to ingest."
        )
    vectors = llm.embed([embedding_text(section) for section in sections], EmbedTask.document)
    handbook_repository.replace_all(
        session,
        [
            HandbookChunk(
                position=position,
                section_title=section.title,
                content=section.content,
                embedding=vector,
            )
            for position, (section, vector) in enumerate(zip(sections, vectors, strict=True))
        ],
    )
    session.commit()
    return len(sections)


def search_policy(
    session: Session, llm: LLM, query: str, *, limit: int = DEFAULT_MATCHES
) -> list[PolicyMatch]:
    """The handbook sections closest to the question, nearest first, with titles to cite."""
    question = query.strip()
    if not question:
        raise ValidationFailed(ErrorCode.validation_error, "The policy question is empty.")
    [embedding] = llm.embed([question], EmbedTask.query)
    return [
        PolicyMatch(chunk.section_title, chunk.content, round(1 - distance, SCORE_DECIMALS))
        for chunk, distance in handbook_repository.search(session, embedding, limit)
    ]
