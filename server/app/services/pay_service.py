"""Pay reports: load the right time entries and hand them to the pure `pay.calculate`.

An entry belongs to a range if its work day does (the Asia/Jerusalem date of clock_in), so a range
includes the whole of an entry that crosses midnight at its end. Open entries (no clock-out) have no
duration yet: they are excluded from the calculation and reported as a count (plan 001, question 8).
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import ErrorCode, NotFound, ValidationFailed
from app.core.time import day_bounds
from app.models import TimeEntry, User
from app.pay import Entry, PayBreakdown, calculate
from app.repositories import time_entry_repository, user_repository
from app.services.authorization import ensure_manager, ensure_self_or_manager


@dataclass(frozen=True)
class UserPay:
    user: User
    breakdown: PayBreakdown
    open_entries: int


def get_pay(
    session: Session,
    current_user: User,
    *,
    from_day: date,
    to_day: date,
    user_id: int | None = None,
) -> UserPay:
    """Pay of `user_id` (default: the current user) for the work days from_day..to_day inclusive."""
    target_id = current_user.id if user_id is None else user_id
    ensure_self_or_manager(current_user, target_id)
    user = user_repository.get_by_id(session, target_id)
    if user is None:
        raise NotFound(ErrorCode.user_not_found, f"User {target_id} does not exist.")
    start, end = range_bounds(from_day, to_day)

    entries = time_entry_repository.list_for_user(session, target_id, start, end)
    return user_pay(user, entries)


def get_team_pay(
    session: Session, current_user: User, *, from_day: date, to_day: date
) -> list[UserPay]:
    """Pay of every active user, plus deactivated users who worked in the range, ordered by name."""
    ensure_manager(current_user)
    start, end = range_bounds(from_day, to_day)

    entries_by_user: dict[int, list[TimeEntry]] = defaultdict(list)
    for entry in time_entry_repository.list_in_range(session, start, end):
        entries_by_user[entry.user_id].append(entry)
    users = user_repository.list_active_or_in(session, set(entries_by_user))
    return [user_pay(user, entries_by_user[user.id]) for user in users]


def range_bounds(from_day: date, to_day: date) -> tuple[datetime, datetime]:
    """UTC instants [start, end) covering the local work days from_day..to_day inclusive."""
    if from_day > to_day:
        raise ValidationFailed(ErrorCode.validation_error, "'from' must not be after 'to'.")
    zone = get_settings().tz
    return day_bounds(from_day, zone)[0], day_bounds(to_day, zone)[1]


def user_pay(user: User, entries: list[TimeEntry]) -> UserPay:
    closed = [Entry(e.clock_in, e.clock_out) for e in entries if e.clock_out is not None]
    settings = get_settings()
    try:
        breakdown = calculate(closed, user.hourly_rate, settings.pay_rules, settings.tz)
    except ValueError as error:  # impossible input from the pure module becomes a domain error
        raise ValidationFailed(ErrorCode.validation_error, str(error)) from error
    return UserPay(user=user, breakdown=breakdown, open_entries=len(entries) - len(closed))
