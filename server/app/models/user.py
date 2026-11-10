from decimal import Decimal

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import Role
from app.models.base import Base, IdMixin, text_enum


class User(IdMixin, Base):
    """A person who can log in. Users are deactivated, never deleted (FKs to users RESTRICT)."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[Role] = mapped_column(text_enum(Role, "role"))
    hourly_rate: Mapped[Decimal]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
