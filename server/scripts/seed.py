"""Seed demo data. Idempotent: running it again changes nothing (until the calendar moves on).

    cd server && uv run python scripts/seed.py

Creates one manager and five employees with different hourly rates (all with the password in
`SEED_PASSWORD`), shift templates, shifts for the current and next week, next week's availability
and time entries for the previous and current month: standard days, overtime days, a split shift
and a shift crossing midnight, plus one manual correction by the manager. Every record is looked up
by its natural key before it is inserted, and existing users are never changed.
"""

import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

# `python scripts/seed.py` puts scripts/ on sys.path, not the server root that holds `app`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.core.enums import AvailabilityStatus, Role, TimeEntrySource  # noqa: E402
from app.core.security import DEFAULT_BCRYPT_ROUNDS, hash_password  # noqa: E402
from app.core.time import week_start, weekday_sunday_based  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Availability, Shift, ShiftTemplate, TimeEntry, User  # noqa: E402

EMAIL_DOMAIN = "shibutzim.example"
MANAGER = ("Dana Levi", Decimal("70.00"))
EMPLOYEES = [
    ("Noa Katz", Decimal("42.50")),
    ("Omer Barak", Decimal("38.00")),
    ("Tamar Mizrahi", Decimal("45.00")),
    ("Yonatan Peretz", Decimal("40.00")),
    ("Lior Ben-David", Decimal("55.00")),
]

# (name, weekday 0 = Sunday, start, end, required staff); an end at or before start ends next day.
SHIFT_TEMPLATES = [
    *[
        (name, day, start, end, staff)
        for day in range(5)
        for name, start, end, staff in (
            ("Morning", time(7, 0), time(15, 0), 2),
            ("Evening", time(15, 0), time(23, 0), 2),
            ("Night", time(23, 0), time(7, 0), 1),
        )
    ],
    ("Friday morning", 5, time(7, 0), time(13, 0), 1),
]

# Local-time segments of one work day; an end at or before the start crosses midnight.
DAY_PATTERNS = {
    "standard": [("08:00", "16:00")],  # 8h
    "overtime": [("08:00", "18:30")],  # 10.5h: 8h + 2h at 125 % + 0.5h at 150 %
    "long": [("07:00", "19:00")],  # 12h
    "split": [("07:00", "11:00"), ("16:00", "22:00")],  # 4h + 6h = 10h on one work day
    "night": [("22:00", "06:00")],  # 8h crossing midnight, belongs to the day it started
}
PATTERN_ROTATION = [
    "standard", "standard", "overtime", "standard", "split",
    "standard", "night", "standard", "long", "standard",
]  # fmt: skip
WORKING_WEEKDAYS = range(5)  # Sunday-Thursday
DAY_OFF_CYCLE = 6  # each employee has a rotating extra day off
MANUAL_NOTE = "Forgot to clock out - corrected by the manager"

AVAILABILITY_CYCLE = [
    AvailabilityStatus.available,
    AvailabilityStatus.preferred,
    AvailabilityStatus.unavailable,
    None,  # no answer, which counts as unavailable
]


@dataclass
class SeedReport:
    created: dict[str, int] = field(default_factory=dict)
    existing: dict[str, int] = field(default_factory=dict)

    def record(self, table: str, created: bool) -> None:
        bucket = self.created if created else self.existing
        bucket[table] = bucket.get(table, 0) + 1


def seed_all(session: Session, *, now: datetime, rounds: int = DEFAULT_BCRYPT_ROUNDS) -> SeedReport:
    """Seed everything as of `now` and commit. `rounds` is the bcrypt cost (tests lower it)."""
    report = SeedReport()
    tz = get_settings().tz
    today = now.astimezone(tz).date()

    manager = seed_user(session, report, *MANAGER, role=Role.manager, rounds=rounds)
    employees = [
        seed_user(session, report, name, rate, role=Role.employee, rounds=rounds)
        for name, rate in EMPLOYEES
    ]
    templates = [seed_shift_template(session, report, *spec) for spec in SHIFT_TEMPLATES]

    this_week = week_start(today)
    shifts_by_week = {
        week: [seed_shift(session, report, template, week) for template in templates]
        for week in (this_week, this_week + timedelta(days=7))
    }
    seed_availability(session, report, employees, shifts_by_week[this_week + timedelta(days=7)])
    seed_time_entries(session, report, manager, employees, today=today, now=now)

    session.commit()
    return report


# --- users, templates, shifts, availability ---


def seed_user(
    session: Session, report: SeedReport, name: str, rate: Decimal, *, role: Role, rounds: int
) -> User:
    email = f"{name.split()[0].lower()}@{EMAIL_DOMAIN}"
    user = session.scalar(select(User).where(User.email == email))
    report.record("users", user is None)
    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(get_settings().seed_password, rounds=rounds),
            name=name,
            role=role,
            hourly_rate=rate,
            is_active=True,
        )
        session.add(user)
        session.flush()
    return user


def seed_shift_template(
    session: Session,
    report: SeedReport,
    name: str,
    weekday: int,
    start: time,
    end: time,
    required_staff: int,
) -> ShiftTemplate:
    template = session.scalar(
        select(ShiftTemplate).where(ShiftTemplate.name == name, ShiftTemplate.weekday == weekday)
    )
    report.record("shift_templates", template is None)
    if template is None:
        template = ShiftTemplate(
            name=name,
            weekday=weekday,
            start_time=start,
            end_time=end,
            required_staff=required_staff,
            is_active=True,
        )
        session.add(template)
        session.flush()
    return template


def seed_shift(session: Session, report: SeedReport, template: ShiftTemplate, week: date) -> Shift:
    """The concrete shift of `template` in the week starting `week`, snapshotting its values."""
    shift = session.scalar(
        select(Shift).where(Shift.template_id == template.id, Shift.week_start == week)
    )
    report.record("shifts", shift is None)
    if shift is None:
        day = week + timedelta(days=template.weekday)
        end_day = day + timedelta(days=1) if template.end_time <= template.start_time else day
        shift = Shift(
            template_id=template.id,
            week_start=week,
            starts_at=local_to_utc(day, template.start_time),
            ends_at=local_to_utc(end_day, template.end_time),
            required_staff=template.required_staff,
        )
        session.add(shift)
        session.flush()
    return shift


def seed_availability(
    session: Session, report: SeedReport, employees: list[User], shifts: list[Shift]
) -> None:
    for employee_index, employee in enumerate(employees):
        for shift_index, shift in enumerate(shifts):
            status = AVAILABILITY_CYCLE[(employee_index + shift_index) % len(AVAILABILITY_CYCLE)]
            if status is None:
                continue
            existing = session.scalar(
                select(Availability).where(
                    Availability.shift_id == shift.id, Availability.user_id == employee.id
                )
            )
            report.record("availabilities", existing is None)
            if existing is None:
                session.add(Availability(shift_id=shift.id, user_id=employee.id, status=status))
    session.flush()


# --- time entries ---


def seed_time_entries(
    session: Session,
    report: SeedReport,
    manager: User,
    employees: list[User],
    *,
    today: date,
    now: datetime,
) -> None:
    """Entries from the first of last month up to yesterday; nothing that ends after `now`."""
    first_day = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    known = {
        (user_id, clock_in)
        for user_id, clock_in in session.execute(
            select(TimeEntry.user_id, TimeEntry.clock_in).where(
                TimeEntry.user_id.in_([e.id for e in employees])
            )
        )
    }
    manual_pending = True  # the first entry of the first employee is the manager's correction
    for employee_index, employee in enumerate(employees):
        for clock_in, clock_out in work_segments(employee_index, first_day, today):
            if clock_out > now:
                continue
            is_manual = manual_pending and employee_index == 0
            manual_pending = manual_pending and not is_manual
            created = (employee.id, clock_in) not in known
            report.record("time_entries", created)
            if created:
                session.add(
                    TimeEntry(
                        user_id=employee.id,
                        clock_in=clock_in,
                        clock_out=clock_out,
                        source=TimeEntrySource.manual if is_manual else TimeEntrySource.clock,
                        created_by=manager.id if is_manual else employee.id,
                        note=MANUAL_NOTE if is_manual else None,
                    )
                )
    session.flush()


def work_segments(
    employee_index: int, first_day: date, today: date
) -> Iterable[tuple[datetime, datetime]]:
    """(clock_in, clock_out) in UTC for each shift worked by one employee, oldest first.

    Fully determined by the calendar date and the employee's position, so a re-run reproduces them.
    """
    day = first_day
    while day < today:
        ordinal = day.toordinal()
        works = weekday_sunday_based(day) in WORKING_WEEKDAYS
        if works and (ordinal + employee_index) % DAY_OFF_CYCLE != 0:
            pattern = PATTERN_ROTATION[(ordinal + employee_index * 3) % len(PATTERN_ROTATION)]
            for start, end in DAY_PATTERNS[pattern]:
                yield day_segment(day, start, end)
        day += timedelta(days=1)


def day_segment(day: date, start: str, end: str) -> tuple[datetime, datetime]:
    start_time, end_time = parse_hhmm(start), parse_hhmm(end)
    end_day = day + timedelta(days=1) if end_time <= start_time else day
    return local_to_utc(day, start_time), local_to_utc(end_day, end_time)


def parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def local_to_utc(day: date, at: time) -> datetime:
    return datetime.combine(day, at, tzinfo=get_settings().tz).astimezone(UTC)


# --- entry point ---


def main() -> None:
    with SessionLocal() as session:
        report = seed_all(session, now=datetime.now(UTC))
    for table in sorted(report.created.keys() | report.existing.keys()):
        created, existing = report.created.get(table, 0), report.existing.get(table, 0)
        print(f"{table:16} created {created:4}  already there {existing:4}")


if __name__ == "__main__":
    main()
