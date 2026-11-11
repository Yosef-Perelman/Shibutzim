"""Shift templates: the recurring slots a week's shifts are generated from (managers only).

A template is deactivated, never deleted, because shifts reference it. Editing a template never
rewrites shifts that were already generated: shifts snapshot its times and staff (architecture §5).
"""

from datetime import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import ErrorCode, NotFound
from app.models import ShiftTemplate, User
from app.repositories import shift_template_repository
from app.services.authorization import ensure_manager

UPDATABLE_FIELDS = ("name", "weekday", "start_time", "end_time", "required_staff", "is_active")


def list_shift_templates(
    session: Session, current_user: User, *, active_only: bool = False
) -> list[ShiftTemplate]:
    ensure_manager(current_user)
    return shift_template_repository.list_templates(session, active_only=active_only)


def create_shift_template(
    session: Session,
    current_user: User,
    *,
    name: str,
    weekday: int,
    start_time: time,
    end_time: time,
    required_staff: int,
) -> ShiftTemplate:
    ensure_manager(current_user)
    template = ShiftTemplate(
        name=name,
        weekday=weekday,
        start_time=start_time,
        end_time=end_time,
        required_staff=required_staff,
        is_active=True,
    )
    session.add(template)
    session.commit()
    return template


def update_shift_template(
    session: Session, current_user: User, template_id: int, *, changes: dict[str, Any]
) -> ShiftTemplate:
    ensure_manager(current_user)
    template = shift_template_repository.get_by_id(session, template_id)
    if template is None:
        raise NotFound(
            ErrorCode.shift_template_not_found, f"Shift template {template_id} does not exist."
        )
    for field in UPDATABLE_FIELDS:
        if field in changes:
            setattr(template, field, changes[field])
    session.commit()
    return template
