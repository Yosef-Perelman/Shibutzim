from collections.abc import Collection

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.models import User


def get_by_id(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)


def get_by_email(session: Session, email: str) -> User | None:
    """`email` must already be normalized (stripped, lowercase) – emails are stored lowercase."""
    return session.scalar(select(User).where(User.email == email))


def add(session: Session, user: User) -> User:
    """Insert and flush, so a duplicate email surfaces here as an `IntegrityError`."""
    session.add(user)
    session.flush()
    return user


def list_active_or_in(session: Session, user_ids: set[int]) -> list[User]:
    """Active users plus the given ids (e.g. deactivated users who still have entries), by name."""
    return list(
        session.scalars(
            select(User)
            .where(or_(User.is_active, User.id.in_(user_ids)))
            .order_by(User.name, User.id)
        )
    )


def get_many(session: Session, user_ids: Collection[int]) -> list[User]:
    return list(session.scalars(select(User).where(User.id.in_(user_ids))))


def list_active_employees(session: Session) -> list[User]:
    """The people the scheduler may place on shifts: active users with the employee role."""
    query = select(User).where(User.role == Role.employee, User.is_active)
    return list(session.scalars(query.order_by(User.id)))


def list_users(
    session: Session, *, role: Role | None = None, is_active: bool | None = None
) -> list[User]:
    """Users filtered by the given fields (None means "any"), by name, then id."""
    query = select(User)
    if role is not None:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    return list(session.scalars(query.order_by(User.name, User.id)))
