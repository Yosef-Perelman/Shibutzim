"""Declarative base shared by every model; fixes column types and constraint names."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Enum, Identity, MetaData, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Deterministic names make migrations reviewable and downgrades reliable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {
        datetime: DateTime(timezone=True),  # timestamptz, always UTC
        Decimal: Numeric(10, 2),  # money
        dict[str, Any]: JSONB,
    }


class IdMixin:
    id: Mapped[int] = mapped_column(Identity(), primary_key=True)


def text_enum(enum: type[StrEnum], name: str) -> Enum:
    """An enum stored as text with a CHECK constraint, so adding a value is a plain migration."""
    return Enum(
        enum,
        name=name,
        native_enum=False,
        length=20,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )
