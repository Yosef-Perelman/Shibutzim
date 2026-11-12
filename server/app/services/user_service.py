"""Listing users for managers (the schedule board's employee picker, plan 003)."""

from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.errors import ErrorCode, ValidationFailed
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


def find_active_employee(session: Session, current_user: User, name: str) -> User:
    """Managers only: the active employee a manager means by `name`.

    The full name wins; otherwise a first or last name matches, in any case. More than one match is
    an error that lists them, so the caller can ask which one.
    """
    ensure_manager(current_user)
    employees = user_repository.list_users(session, role=Role.employee, is_active=True)
    wanted = name.strip().casefold()
    matches = [user for user in employees if user.name.casefold() == wanted]
    matches = matches or [user for user in employees if wanted in user.name.casefold().split()]
    if len(matches) == 1:
        return matches[0]
    if matches:
        names = ", ".join(sorted(user.name for user in matches))
        raise ValidationFailed(
            ErrorCode.validation_error,
            f"Several employees match '{name}': {names}. Ask the manager which one.",
        )
    names = ", ".join(user.name for user in employees)
    raise ValidationFailed(
        ErrorCode.user_not_assignable,
        f"No active employee is called '{name}'. Active employees: {names}.",
    )
