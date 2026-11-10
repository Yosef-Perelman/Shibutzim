"""The seed script: idempotent, realistic, and consistent with the pay rules."""

from collections import defaultdict
from datetime import UTC, date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.enums import Role, TimeEntrySource
from app.core.security import verify_password
from app.models import Availability, Shift, ShiftTemplate, TimeEntry, User
from app.services import pay_service
from scripts import seed
from tests.factories import NOW, TEST_BCRYPT_ROUNDS

TZ = get_settings().tz
FIRST_DAY, LAST_DAY = (
    date(2026, 2, 1),
    date(2026, 3, 8),
)  # last month and this month up to yesterday


def run_seed(session: Session, **kwargs) -> seed.SeedReport:
    return seed.seed_all(session, now=kwargs.pop("now", NOW), rounds=TEST_BCRYPT_ROUNDS, **kwargs)


def count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def table_counts(session: Session) -> dict[str, int]:
    return {
        model.__tablename__: count(session, model)
        for model in (User, ShiftTemplate, Shift, Availability, TimeEntry)
    }


@pytest.fixture
def seeded(session: Session) -> Session:
    run_seed(session)
    return session


# --- idempotency ---


def test_running_the_seed_twice_changes_no_row_counts(session: Session) -> None:
    run_seed(session)
    first = table_counts(session)

    second_report = run_seed(session)

    assert table_counts(session) == first
    assert second_report.created == {}


def test_the_first_run_creates_every_kind_of_row(session: Session) -> None:
    report = run_seed(session)

    assert set(report.created) == {
        "users",
        "shift_templates",
        "shifts",
        "availabilities",
        "time_entries",
    }
    assert report.existing == {}


def test_the_seed_never_overwrites_an_existing_user(seeded: Session) -> None:
    noa = seeded.scalar(select(User).where(User.email == "noa@shibutzim.example"))
    noa.hourly_rate = Decimal("99.00")
    seeded.flush()

    run_seed(seeded)

    assert noa.hourly_rate == Decimal("99.00")


def test_a_later_run_only_adds_the_new_days(seeded: Session) -> None:
    before = set(seeded.execute(select(TimeEntry.user_id, TimeEntry.clock_in)))

    run_seed(seeded, now=NOW + timedelta(days=3))

    after = list(seeded.execute(select(TimeEntry.user_id, TimeEntry.clock_in)))
    assert before <= set(after)
    assert len(after) == len(set(after)) > len(before)


# --- users ---


def test_one_manager_and_five_employees_with_different_hourly_rates(seeded: Session) -> None:
    users = list(seeded.scalars(select(User)))

    managers = [u for u in users if u.role is Role.manager]
    employees = [u for u in users if u.role is Role.employee]
    assert len(managers) == 1
    assert len(employees) == 5
    assert len({u.hourly_rate for u in employees}) == 5


def test_every_user_can_log_in_with_the_seed_password(seeded: Session) -> None:
    password = get_settings().seed_password

    assert all(verify_password(password, u.password_hash) for u in seeded.scalars(select(User)))


def test_emails_are_lowercase_and_unique(seeded: Session) -> None:
    emails = list(seeded.scalars(select(User.email)))

    assert emails == [e.lower() for e in emails]
    assert len(emails) == len(set(emails)) == 6


# --- templates, shifts, availability ---


def test_shifts_exist_for_the_current_and_next_week(seeded: Session) -> None:
    weeks = set(seeded.scalars(select(Shift.week_start)))

    assert weeks == {date(2026, 3, 8), date(2026, 3, 15)}  # both Sundays
    assert count(seeded, Shift) == 2 * count(seeded, ShiftTemplate)


def test_the_night_shift_ends_the_next_morning(seeded: Session) -> None:
    night = seeded.scalar(
        select(Shift).join(ShiftTemplate).where(ShiftTemplate.name == "Night").limit(1)
    )

    assert night.ends_at - night.starts_at == timedelta(hours=8)
    assert night.starts_at.astimezone(TZ).hour == 23


def test_shifts_snapshot_the_template_values(seeded: Session) -> None:
    shift = seeded.scalar(select(Shift).limit(1))
    template = seeded.get(ShiftTemplate, shift.template_id)

    assert shift.required_staff == template.required_staff
    assert shift.starts_at.astimezone(TZ).time() == template.start_time


def test_availability_covers_next_week_with_mixed_answers_and_gaps(seeded: Session) -> None:
    next_week_shifts = count(seeded, Shift) // 2
    answers = list(seeded.scalars(select(Availability)))

    statuses = {a.status.value for a in answers}
    assert statuses == {"available", "preferred", "unavailable"}
    assert len(answers) < 5 * next_week_shifts  # some employees gave no answer
    assert {s.week_start for s in (seeded.get(Shift, a.shift_id) for a in answers)} == {
        date(2026, 3, 15)
    }


# --- time entries ---


def entries_by_user_and_day(session: Session) -> dict[tuple[int, date], list[TimeEntry]]:
    grouped = defaultdict(list)
    for entry in session.scalars(select(TimeEntry).order_by(TimeEntry.clock_in)):
        grouped[(entry.user_id, entry.clock_in.astimezone(TZ).date())].append(entry)
    return grouped


def test_entries_cover_last_month_and_this_month_until_yesterday(seeded: Session) -> None:
    days = {day for _, day in entries_by_user_and_day(seeded)}

    assert min(days) >= FIRST_DAY and max(days) <= LAST_DAY
    assert {d.month for d in days} == {2, 3}


def test_all_entries_are_closed_and_none_ends_in_the_future(seeded: Session) -> None:
    entries = list(seeded.scalars(select(TimeEntry)))

    assert all(e.clock_out is not None and e.clock_out <= NOW for e in entries)
    assert all(timedelta(0) < e.clock_out - e.clock_in <= timedelta(hours=24) for e in entries)


def test_the_seed_contains_a_split_shift(seeded: Session) -> None:
    assert any(len(entries) == 2 for entries in entries_by_user_and_day(seeded).values())


def test_the_seed_contains_an_entry_crossing_midnight(seeded: Session) -> None:
    crossing = [
        e
        for e in seeded.scalars(select(TimeEntry))
        if e.clock_out.astimezone(TZ).date() != e.clock_in.astimezone(TZ).date()
    ]

    assert crossing


def test_the_seed_contains_overtime_days_that_pay_more_than_the_base_rate(seeded: Session) -> None:
    manager = seeded.scalar(select(User).where(User.role == Role.manager))
    employee = seeded.scalar(select(User).where(User.email == "noa@shibutzim.example"))

    report = pay_service.get_pay(
        seeded, manager, user_id=employee.id, from_day=FIRST_DAY, to_day=LAST_DAY
    )

    overtime_days = [d for d in report.breakdown.days if len(d.lines) > 1]
    assert overtime_days
    assert report.breakdown.amount > employee.hourly_rate * Decimal(report.breakdown.seconds) / 3600


def test_pay_can_be_calculated_for_the_whole_seeded_team(seeded: Session) -> None:
    manager = seeded.scalar(select(User).where(User.role == Role.manager))

    team = pay_service.get_team_pay(seeded, manager, from_day=FIRST_DAY, to_day=LAST_DAY)

    employees = [row for row in team if row.user.role is Role.employee]
    assert len(employees) == 5
    assert all(row.breakdown.amount > 0 and row.open_entries == 0 for row in employees)


def test_no_employee_has_overlapping_entries(seeded: Session) -> None:
    by_user = defaultdict(list)
    for entry in seeded.scalars(select(TimeEntry).order_by(TimeEntry.clock_in)):
        by_user[entry.user_id].append(entry)

    for entries in by_user.values():
        for earlier, later in zip(entries, entries[1:], strict=False):
            assert earlier.clock_out <= later.clock_in


def test_exactly_one_entry_is_a_manual_correction_by_the_manager(seeded: Session) -> None:
    manager = seeded.scalar(select(User).where(User.role == Role.manager))

    manual = list(
        seeded.scalars(select(TimeEntry).where(TimeEntry.source == TimeEntrySource.manual))
    )

    assert len(manual) == 1
    assert manual[0].created_by == manager.id
    assert manual[0].note == seed.MANUAL_NOTE


def test_the_manager_has_no_time_entries(seeded: Session) -> None:
    manager = seeded.scalar(select(User).where(User.role == Role.manager))

    assert count_entries_of(seeded, manager) == 0


def count_entries_of(session: Session, user: User) -> int:
    return session.scalar(
        select(func.count()).select_from(TimeEntry).where(TimeEntry.user_id == user.id)
    )


def test_entries_use_utc_aware_timestamps(seeded: Session) -> None:
    entry = seeded.scalar(select(TimeEntry).limit(1))

    assert entry.clock_in.utcoffset() is not None
    assert entry.clock_in.astimezone(UTC).tzinfo is UTC
