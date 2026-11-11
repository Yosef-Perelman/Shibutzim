from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ShiftTemplate


def get_by_id(session: Session, template_id: int) -> ShiftTemplate | None:
    return session.get(ShiftTemplate, template_id)


def list_templates(session: Session, *, active_only: bool = False) -> list[ShiftTemplate]:
    """Templates by weekday, then start time, then id."""
    query = select(ShiftTemplate)
    if active_only:
        query = query.where(ShiftTemplate.is_active)
    order = (ShiftTemplate.weekday, ShiftTemplate.start_time, ShiftTemplate.id)
    return list(session.scalars(query.order_by(*order)))
