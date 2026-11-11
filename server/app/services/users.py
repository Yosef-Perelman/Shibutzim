"""Small user lookups and checks shared by services."""

from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.errors import ErrorCode, NotFound, ValidationFailed
from app.models import User
from app.repositories import user_repository


def get_user_or_404(session: Session, user_id: int) -> User:
    user = user_repository.get_by_id(session, user_id)
    if user is None:
        raise NotFound(ErrorCode.user_not_found, f"User {user_id} does not exist.")
    return user


def ensure_assignable(user: User) -> None:
    """Only active employees take part in scheduling: managers are never placed on shifts."""
    if user.role is not Role.employee or not user.is_active:
        raise ValidationFailed(
            ErrorCode.user_not_assignable, f"{user.name} is not an active employee."
        )
