"""Authorization checks. Services call these first, before loading or changing anything."""

from app.core.enums import Role
from app.core.errors import ErrorCode, Forbidden
from app.models import User


def ensure_manager(user: User) -> None:
    """Team-level operations are for managers only."""
    if user.role is not Role.manager:
        raise Forbidden(ErrorCode.forbidden, "This action is for managers only.")


def ensure_self_or_manager(user: User, target_user_id: int) -> None:
    """Personal data is visible to its owner and to managers."""
    if user.role is not Role.manager and user.id != target_user_id:
        raise Forbidden(ErrorCode.forbidden, "You may only access your own data.")
