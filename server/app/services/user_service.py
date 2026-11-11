"""Listing users for managers (the schedule board's employee picker, plan 003)."""

from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models import User
from app.repositories import user_repository
from app.services.authorization import ensure_manager


def list_users(
    session: Session,
    current_user: User,
    *,
    role: Role | None = None,
    is_active: bool | None = None,
) -> list[User]:
    """Managers only: every user, optionally filtered by role and active state, by name."""
    ensure_manager(current_user)
    return user_repository.list_users(session, role=role, is_active=is_active)
