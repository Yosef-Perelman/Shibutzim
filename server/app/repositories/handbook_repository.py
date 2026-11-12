from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import HandbookChunk


def replace_all(session: Session, chunks: Sequence[HandbookChunk]) -> None:
    """Swap the whole handbook for `chunks`; it is always re-ingested as a unit."""
    session.execute(delete(HandbookChunk))
    session.add_all(chunks)
    session.flush()


def search(
    session: Session, embedding: Sequence[float], limit: int
) -> list[tuple[HandbookChunk, float]]:
    """The `limit` chunks closest to `embedding` by cosine distance, nearest first."""
    distance = HandbookChunk.embedding.cosine_distance(list(embedding)).label("distance")
    query = select(HandbookChunk, distance).order_by(distance, HandbookChunk.position).limit(limit)
    return [(chunk, float(value)) for chunk, value in session.execute(query)]
