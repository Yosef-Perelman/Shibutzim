"""Shifts: the concrete slots of one week, generated from the active shift templates.

Times are computed in the configured zone (`Asia/Jerusalem`) and stored in UTC; each shift
snapshots its template's times and `required_staff` (architecture §5, §6.2).
"""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import ErrorCode, NotFound
from app.core.time import shift_bounds
from app.models import Shift, ShiftTemplate, User
from app.repositories import shift_repository, shift_template_repository
from app.services.authorization import ensure_manager
from app.services.weeks import ensure_week_start

WEEK_TEMPLATE_INDEX = "uq_shifts_template_id_week_start"


@dataclass(frozen=True)
class GeneratedShifts:
    created: int
    shifts: list[Shift]  # every shift of the week, earliest first


def generate_shifts(session: Session, current_user: User, week_start: date) -> GeneratedShifts:
    """Create the week's missing shifts. Running it again adds only what is still missing."""
    ensure_manager(current_user)
    ensure_week_start(week_start)

    present = {shift.template_id for shift in shift_repository.list_for_week(session, week_start)}
    templates = shift_template_repository.list_templates(session, active_only=True)
    created = sum(
        add_shift(session, template, week_start)
        for template in templates
        if template.id not in present
    )
    session.commit()
    return GeneratedShifts(created, shift_repository.list_for_week(session, week_start))


def get_shift(session: Session, current_user: User, shift_id: int) -> Shift:
    """Every signed-in user may see a shift."""
    shift = shift_repository.get_by_id(session, shift_id)
    if shift is None:
        raise NotFound(ErrorCode.shift_not_found, f"Shift {shift_id} does not exist.")
    return shift


def list_shifts(session: Session, current_user: User, week_start: date) -> list[Shift]:
    """Every signed-in user may see the shifts of a week."""
    ensure_week_start(week_start)
    return shift_repository.list_for_week(session, week_start)


def add_shift(session: Session, template: ShiftTemplate, week_start: date) -> bool:
    """Insert the template's shift for the week; False if a concurrent request already did."""
    day = week_start + timedelta(days=template.weekday)
    starts_at, ends_at = shift_bounds(
        day, template.start_time, template.end_time, get_settings().tz
    )
    shift = Shift(
        template_id=template.id,
        week_start=week_start,
        starts_at=starts_at,
        ends_at=ends_at,
        required_staff=template.required_staff,
    )
    try:
        with session.begin_nested():
            session.add(shift)
            session.flush()
    except IntegrityError as error:
        # Two simultaneous generates both saw the shift missing; the unique constraint stops one.
        if WEEK_TEMPLATE_INDEX in str(error.orig):
            return False
        raise
    return True
