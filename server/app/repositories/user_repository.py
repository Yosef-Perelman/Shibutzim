from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import User


def get_by_id(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)


def get_by_email(session: Session, email: str) -> User | None:
    """`email` must already be normalized (stripped, lowercase) – emails are stored lowercase."""
    return session.scalar(select(User).where(User.email == email))


def list_active_or_in(session: Session, user_ids: set[int]) -> list[User]:
    """Active users plus the given ids (e.g. deactivated users who still have entries), by name."""
    return list(
        session.scalars(
            select(User)
            .where(or_(User.is_active, User.id.in_(user_ids)))
            .order_by(User.name, User.id)
        )
    )
