from pgvector.sqlalchemy import Vector
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin

EMBEDDING_DIMENSIONS = 768  # plan 001, open question 6


class HandbookChunk(IdMixin, Base):
    """One handbook section with its embedding."""

    __tablename__ = "handbook_chunks"

    section_title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    position: Mapped[int] = mapped_column(Integer)
