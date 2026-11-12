"""Listing, adding and deactivating users: managers only (plans 003 and 005)."""

from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.errors import Conflict, ErrorCode, ValidationFailed
from app.core.security import hash_password
from app.models import User
from app.repositories import user_repository
from app.services.auth_service import normalize_email
from app.services.authorization import ensure_manager
from app.services.users import get_user_or_404

EMAIL_UNIQUE_INDEX = "uq_users_email"
EMAIL_TAKEN_MESSAGE = "Another person already uses this email."
CANNOT_DEACTIVATE_SELF_MESSAGE = "You cannot deactivate your own account."


def create_user(
    session: Session,
    current_user: User,
    *,
    email: str,
    name: str,
    role: Role,
    hourly_rate: Decimal,
    password: str,
) -> User:
    """Managers only: add a person who can sign in with the initial `password`."""
    ensure_manager(current_user)
    email = normalize_email(email)
    if user_repository.get_by_email(session, email):
        raise Conflict(ErrorCode.email_already_used, EMAIL_TAKEN_MESSAGE)

    user = User(
        email=email,
        password_hash=hash_password(password),
        name=name.strip(),
        role=role,
        hourly_rate=hourly_rate,
        is_active=True,
    )
    try:
        with session.begin_nested():
            user_repository.add(session, user)
    except IntegrityError as error:
        # Two simultaneous requests can both pass the check above; the unique index stops one.
        if EMAIL_UNIQUE_INDEX in str(error.orig):
            raise Conflict(ErrorCode.email_already_used, EMAIL_TAKEN_MESSAGE) from error
        raise
    session.commit()
    return user


def set_user_active(session: Session, current_user: User, user_id: int, *, is_active: bool) -> User:
    """Managers only: deactivate or reactivate a person; history stays, sign-in stops."""
    ensure_manager(current_user)
    user = get_user_or_404(session, user_id)
    if user.id == current_user.id and not is_active:
        raise ValidationFailed(ErrorCode.cannot_deactivate_self, CANNOT_DEACTIVATE_SELF_MESSAGE)
    user.is_active = is_active
    session.commit()
    return user


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
