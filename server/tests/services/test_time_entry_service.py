"""Time-entry business rules and authorization (product-definition §5.3)."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.enums import Role, TimeEntrySource
from app.core.errors import Conflict, ErrorCode, Forbidden, NotFound, ValidationFailed
from app.models import User
from app.repositories import time_entry_repository
from app.services import time_entry_service as service
from tests.factories import NOW, make_time_entry, make_user

HOUR = timedelta(hours=1)


def at(hour: int, *, day: int = 9) -> datetime:
    return datetime(2026, 3, day, hour, 0, tzinfo=UTC)


# --- clock in ---


def test_clock_in_opens_an_entry_for_the_current_user(session: Session, employee: User) -> None:
    entry = service.clock_in(session, employee, now=NOW)

    assert entry.user_id == employee.id
    assert entry.clock_in == NOW
    assert entry.clock_out is None
    assert entry.source is TimeEntrySource.clock
    assert entry.created_by == employee.id


def test_clock_in_twice_is_already_clocked_in(session: Session, employee: User) -> None:
    service.clock_in(session, employee, now=NOW)

    with pytest.raises(Conflict) as raised:
        service.clock_in(session, employee, now=NOW + HOUR)

    assert raised.value.code == ErrorCode.already_clocked_in


def test_clock_in_lost_race_is_already_clocked_in(
    session: Session, employee: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two simultaneous requests both pass the check; the unique index stops the second."""
    make_time_entry(session, employee, clock_in=NOW - HOUR, duration=None)
    monkeypatch.setattr(time_entry_repository, "get_open_entry", lambda *args, **kwargs: None)

    with pytest.raises(Conflict) as raised:
        service.clock_in(session, employee, now=NOW)

    assert raised.value.code == ErrorCode.already_clocked_in


def test_clock_in_inside_a_manual_entry_is_an_overlap(session: Session, employee: User) -> None:
    make_time_entry(session, employee, clock_in=NOW - HOUR, duration=2 * HOUR)

    with pytest.raises(Conflict) as raised:
        service.clock_in(session, employee, now=NOW)

    assert raised.value.code == ErrorCode.time_entry_overlap


def test_clock_in_right_after_an_entry_ended_is_allowed(session: Session, employee: User) -> None:
    make_time_entry(session, employee, clock_in=NOW - 2 * HOUR, duration=2 * HOUR)

    entry = service.clock_in(session, employee, now=NOW)

    assert entry.clock_in == NOW


def test_clock_in_is_not_blocked_by_another_employees_open_entry(
    session: Session, employee: User, other_employee: User
) -> None:
    make_time_entry(session, other_employee, clock_in=NOW - HOUR, duration=None)

    entry = service.clock_in(session, employee, now=NOW)

    assert entry.user_id == employee.id


# --- clock out ---


def test_clock_out_closes_the_open_entry(session: Session, employee: User) -> None:
    opened = make_time_entry(session, employee, clock_in=NOW - 4 * HOUR, duration=None)

    closed = service.clock_out(session, employee, now=NOW)

    assert closed.id == opened.id
    assert closed.clock_out == NOW


def test_clock_out_without_an_open_entry_is_not_clocked_in(
    session: Session, employee: User
) -> None:
    with pytest.raises(Conflict) as raised:
        service.clock_out(session, employee, now=NOW)

    assert raised.value.code == ErrorCode.not_clocked_in


def test_clock_out_with_only_closed_entries_is_not_clocked_in(
    session: Session, employee: User
) -> None:
    make_time_entry(session, employee, clock_in=NOW - 6 * HOUR, duration=HOUR)

    with pytest.raises(Conflict) as raised:
        service.clock_out(session, employee, now=NOW)

    assert raised.value.code == ErrorCode.not_clocked_in


def test_clock_out_ignores_other_employees_open_entries(
    session: Session, employee: User, other_employee: User
) -> None:
    make_time_entry(session, other_employee, clock_in=NOW - HOUR, duration=None)

    with pytest.raises(Conflict) as raised:
        service.clock_out(session, employee, now=NOW)

    assert raised.value.code == ErrorCode.not_clocked_in


def test_clock_out_at_the_same_instant_is_clock_out_before_clock_in(
    session: Session, employee: User
) -> None:
    make_time_entry(session, employee, clock_in=NOW, duration=None)

    with pytest.raises(ValidationFailed) as raised:
        service.clock_out(session, employee, now=NOW)

    assert raised.value.code == ErrorCode.clock_out_before_clock_in


def test_clock_out_after_exactly_24_hours_is_allowed(session: Session, employee: User) -> None:
    make_time_entry(session, employee, clock_in=NOW - timedelta(hours=24), duration=None)

    entry = service.clock_out(session, employee, now=NOW)

    assert entry.clock_out == NOW


def test_clock_out_after_more_than_24_hours_is_entry_too_long(
    session: Session, employee: User
) -> None:
    opened = make_time_entry(session, employee, clock_in=NOW - timedelta(hours=25), duration=None)

    with pytest.raises(ValidationFailed) as raised:
        service.clock_out(session, employee, now=NOW)

    assert raised.value.code == ErrorCode.entry_too_long
    assert opened.clock_out is None  # left for a manager to correct


def test_clock_out_over_a_later_manual_entry_is_an_overlap(
    session: Session, employee: User
) -> None:
    make_time_entry(session, employee, clock_in=NOW - 4 * HOUR, duration=None)
    make_time_entry(session, employee, clock_in=NOW - HOUR, duration=HOUR)

    with pytest.raises(Conflict) as raised:
        service.clock_out(session, employee, now=NOW)

    assert raised.value.code == ErrorCode.time_entry_overlap


# --- manual entry (manager) ---


def test_create_time_entry_records_a_manual_entry_for_the_employee(
    session: Session, manager: User, employee: User
) -> None:
    entry = service.create_time_entry(
        session, manager, user_id=employee.id, clock_in=at(7), clock_out=at(11), note="Forgot"
    )

    assert (entry.user_id, entry.clock_in, entry.clock_out) == (employee.id, at(7), at(11))
    assert entry.source is TimeEntrySource.manual
    assert entry.created_by == manager.id
    assert entry.note == "Forgot"


def test_create_time_entry_by_an_employee_is_forbidden_even_for_themselves(
    session: Session, employee: User
) -> None:
    with pytest.raises(Forbidden):
        service.create_time_entry(
            session, employee, user_id=employee.id, clock_in=at(7), clock_out=at(11)
        )


def test_create_time_entry_for_an_unknown_user_is_user_not_found(
    session: Session, manager: User
) -> None:
    with pytest.raises(NotFound) as raised:
        service.create_time_entry(
            session, manager, user_id=999_999, clock_in=at(7), clock_out=at(11)
        )

    assert raised.value.code == ErrorCode.user_not_found


def test_create_time_entry_allows_a_split_shift_on_one_day(
    session: Session, manager: User, employee: User
) -> None:
    service.create_time_entry(
        session, manager, user_id=employee.id, clock_in=at(5), clock_out=at(9)
    )
    service.create_time_entry(
        session, manager, user_id=employee.id, clock_in=at(14), clock_out=at(20)
    )

    entries = service.list_time_entries(session, manager, user_id=employee.id)
    assert len(entries) == 2


def test_create_time_entry_allows_crossing_midnight(
    session: Session, manager: User, employee: User
) -> None:
    entry = service.create_time_entry(
        session, manager, user_id=employee.id, clock_in=at(20), clock_out=at(4, day=10)
    )

    assert entry.clock_out - entry.clock_in == 8 * HOUR


@pytest.mark.parametrize(
    ("clock_in", "clock_out"),
    [(at(11), at(7)), (at(7), at(7))],
    ids=["out_before_in", "zero_length"],
)
def test_create_time_entry_clock_out_must_be_after_clock_in(
    session: Session, manager: User, employee: User, clock_in: datetime, clock_out: datetime
) -> None:
    with pytest.raises(ValidationFailed) as raised:
        service.create_time_entry(
            session, manager, user_id=employee.id, clock_in=clock_in, clock_out=clock_out
        )

    assert raised.value.code == ErrorCode.clock_out_before_clock_in


def test_create_time_entry_of_exactly_24_hours_is_allowed(
    session: Session, manager: User, employee: User
) -> None:
    entry = service.create_time_entry(
        session, manager, user_id=employee.id, clock_in=at(8), clock_out=at(8, day=10)
    )

    assert entry.clock_out - entry.clock_in == timedelta(hours=24)


def test_create_time_entry_longer_than_24_hours_is_entry_too_long(
    session: Session, manager: User, employee: User
) -> None:
    with pytest.raises(ValidationFailed) as raised:
        service.create_time_entry(
            session, manager, user_id=employee.id, clock_in=at(8), clock_out=at(9, day=10)
        )

    assert raised.value.code == ErrorCode.entry_too_long


@pytest.mark.parametrize(
    ("clock_in", "clock_out"),
    [
        (at(9), at(11)),  # starts inside the existing 08:00-12:00 entry
        (at(11), at(14)),  # starts inside it and runs past its end
        (at(6), at(9)),  # starts before, ends inside
        (at(6), at(14)),  # contains it
        (at(8), at(12)),  # identical
    ],
    ids=["inside", "runs_past_end", "runs_into_start", "contains", "identical"],
)
def test_create_time_entry_overlapping_an_existing_entry_is_rejected(
    session: Session, manager: User, employee: User, clock_in: datetime, clock_out: datetime
) -> None:
    make_time_entry(session, employee, clock_in=at(8), duration=4 * HOUR)

    with pytest.raises(Conflict) as raised:
        service.create_time_entry(
            session, manager, user_id=employee.id, clock_in=clock_in, clock_out=clock_out
        )

    assert raised.value.code == ErrorCode.time_entry_overlap


def test_create_time_entry_touching_an_existing_entry_is_allowed(
    session: Session, manager: User, employee: User
) -> None:
    make_time_entry(session, employee, clock_in=at(8), duration=4 * HOUR)

    before = service.create_time_entry(
        session, manager, user_id=employee.id, clock_in=at(4), clock_out=at(8)
    )
    after = service.create_time_entry(
        session, manager, user_id=employee.id, clock_in=at(12), clock_out=at(16)
    )

    assert (before.clock_out, after.clock_in) == (at(8), at(12))


def test_create_time_entry_overlapping_an_open_entry_is_rejected(
    session: Session, manager: User, employee: User
) -> None:
    make_time_entry(session, employee, clock_in=at(8), duration=None)

    with pytest.raises(Conflict) as raised:
        service.create_time_entry(
            session, manager, user_id=employee.id, clock_in=at(10), clock_out=at(12)
        )

    assert raised.value.code == ErrorCode.time_entry_overlap


def test_create_time_entry_may_overlap_another_employees_entry(
    session: Session, manager: User, employee: User, other_employee: User
) -> None:
    make_time_entry(session, other_employee, clock_in=at(8), duration=4 * HOUR)

    entry = service.create_time_entry(
        session, manager, user_id=employee.id, clock_in=at(9), clock_out=at(11)
    )

    assert entry.user_id == employee.id


# --- correct an entry (manager) ---


def test_update_time_entry_changes_times_and_note(
    session: Session, manager: User, employee: User
) -> None:
    entry = make_time_entry(session, employee, clock_in=at(8), duration=4 * HOUR)

    updated = service.update_time_entry(
        session, manager, entry.id, changes={"clock_in": at(7), "note": "Came early"}
    )

    assert (updated.clock_in, updated.clock_out, updated.note) == (at(7), at(12), "Came early")


def test_update_time_entry_can_close_an_open_entry(
    session: Session, manager: User, employee: User
) -> None:
    entry = make_time_entry(session, employee, clock_in=at(8), duration=None)

    updated = service.update_time_entry(session, manager, entry.id, changes={"clock_out": at(16)})

    assert updated.clock_out == at(16)


def test_update_time_entry_keeps_its_source_and_creator(
    session: Session, manager: User, employee: User
) -> None:
    entry = make_time_entry(session, employee, clock_in=at(8), duration=4 * HOUR)

    updated = service.update_time_entry(session, manager, entry.id, changes={"clock_out": at(13)})

    assert updated.source is TimeEntrySource.clock
    assert updated.created_by == employee.id


def test_update_time_entry_validates_the_merged_interval(
    session: Session, manager: User, employee: User
) -> None:
    entry = make_time_entry(session, employee, clock_in=at(8), duration=4 * HOUR)

    with pytest.raises(ValidationFailed) as raised:
        service.update_time_entry(session, manager, entry.id, changes={"clock_in": at(13)})

    assert raised.value.code == ErrorCode.clock_out_before_clock_in


def test_update_time_entry_cannot_become_longer_than_24_hours(
    session: Session, manager: User, employee: User
) -> None:
    entry = make_time_entry(session, employee, clock_in=at(8), duration=4 * HOUR)

    with pytest.raises(ValidationFailed) as raised:
        service.update_time_entry(session, manager, entry.id, changes={"clock_out": at(9, day=10)})

    assert raised.value.code == ErrorCode.entry_too_long


def test_update_time_entry_cannot_overlap_the_employees_other_entry(
    session: Session, manager: User, employee: User
) -> None:
    make_time_entry(session, employee, clock_in=at(14), duration=4 * HOUR)
    entry = make_time_entry(session, employee, clock_in=at(8), duration=4 * HOUR)

    with pytest.raises(Conflict) as raised:
        service.update_time_entry(session, manager, entry.id, changes={"clock_out": at(15)})

    assert raised.value.code == ErrorCode.time_entry_overlap


def test_update_time_entry_does_not_overlap_itself(
    session: Session, manager: User, employee: User
) -> None:
    entry = make_time_entry(session, employee, clock_in=at(8), duration=4 * HOUR)

    updated = service.update_time_entry(session, manager, entry.id, changes={"clock_out": at(13)})

    assert updated.clock_out == at(13)


def test_update_time_entry_that_does_not_exist_is_time_entry_not_found(
    session: Session, manager: User
) -> None:
    with pytest.raises(NotFound) as raised:
        service.update_time_entry(session, manager, 999_999, changes={"note": "x"})

    assert raised.value.code == ErrorCode.time_entry_not_found


def test_update_time_entry_by_an_employee_is_forbidden(session: Session, employee: User) -> None:
    entry = make_time_entry(session, employee)

    with pytest.raises(Forbidden):
        service.update_time_entry(session, employee, entry.id, changes={"note": "mine"})


def test_update_by_an_employee_does_not_reveal_whether_the_entry_exists(
    session: Session, employee: User
) -> None:
    with pytest.raises(Forbidden):
        service.update_time_entry(session, employee, 999_999, changes={"note": "x"})


# --- delete (manager) ---


def test_delete_time_entry_removes_it(session: Session, manager: User, employee: User) -> None:
    entry = make_time_entry(session, employee)

    service.delete_time_entry(session, manager, entry.id)

    assert service.list_time_entries(session, manager, user_id=employee.id) == []


def test_delete_time_entry_by_an_employee_is_forbidden(session: Session, employee: User) -> None:
    entry = make_time_entry(session, employee)

    with pytest.raises(Forbidden):
        service.delete_time_entry(session, employee, entry.id)


def test_delete_time_entry_that_does_not_exist_is_time_entry_not_found(
    session: Session, manager: User
) -> None:
    with pytest.raises(NotFound) as raised:
        service.delete_time_entry(session, manager, 999_999)

    assert raised.value.code == ErrorCode.time_entry_not_found


# --- list ---


def test_list_defaults_to_the_current_users_entries(
    session: Session, employee: User, other_employee: User
) -> None:
    mine = make_time_entry(session, employee)
    make_time_entry(session, other_employee)

    entries = service.list_time_entries(session, employee)

    assert [entry.id for entry in entries] == [mine.id]


def test_list_lets_an_employee_name_themselves(session: Session, employee: User) -> None:
    mine = make_time_entry(session, employee)

    entries = service.list_time_entries(session, employee, user_id=employee.id)

    assert [entry.id for entry in entries] == [mine.id]


def test_list_for_another_employee_is_forbidden(
    session: Session, employee: User, other_employee: User
) -> None:
    with pytest.raises(Forbidden):
        service.list_time_entries(session, employee, user_id=other_employee.id)


def test_list_lets_a_manager_read_anyone(session: Session, manager: User, employee: User) -> None:
    entry = make_time_entry(session, employee)

    entries = service.list_time_entries(session, manager, user_id=employee.id)

    assert [e.id for e in entries] == [entry.id]


def test_list_of_an_unknown_user_by_a_manager_is_user_not_found(
    session: Session, manager: User
) -> None:
    with pytest.raises(NotFound) as raised:
        service.list_time_entries(session, manager, user_id=999_999)

    assert raised.value.code == ErrorCode.user_not_found


def test_list_is_ordered_by_clock_in(session: Session, employee: User) -> None:
    late = make_time_entry(session, employee, clock_in=at(15), duration=HOUR)
    early = make_time_entry(session, employee, clock_in=at(7), duration=HOUR)

    entries = service.list_time_entries(session, employee)

    assert [e.id for e in entries] == [early.id, late.id]


def test_list_range_uses_the_local_work_day_inclusive(session: Session, employee: User) -> None:
    """Asia/Jerusalem is UTC+2 on these dates, so local midnight is 22:00 UTC the evening before."""
    mar9 = make_time_entry(session, employee, clock_in=at(5), duration=HOUR)  # 07:00 local, Mar 9
    mar10_early = make_time_entry(session, employee, clock_in=at(22), duration=HOUR)  # 00:00 Mar 10
    mar10_late = make_time_entry(session, employee, clock_in=at(21, day=10), duration=HOUR)  # 23:00
    mar11 = make_time_entry(
        session, employee, clock_in=at(22, day=10), duration=HOUR
    )  # 00:00 Mar 11

    only_the_10th = service.list_time_entries(
        session, employee, from_day=date(2026, 3, 10), to_day=date(2026, 3, 10)
    )
    from_the_10th = service.list_time_entries(session, employee, from_day=date(2026, 3, 10))
    up_to_the_9th = service.list_time_entries(session, employee, to_day=date(2026, 3, 9))

    assert [e.id for e in only_the_10th] == [mar10_early.id, mar10_late.id]
    assert [e.id for e in from_the_10th] == [mar10_early.id, mar10_late.id, mar11.id]
    assert [e.id for e in up_to_the_9th] == [mar9.id]


def test_list_puts_a_midnight_crossing_entry_on_the_day_it_started(
    session: Session, employee: User
) -> None:
    crossing = make_time_entry(
        session, employee, clock_in=at(20), duration=8 * HOUR
    )  # 22:00 -> 06:00

    on_start_day = service.list_time_entries(
        session, employee, from_day=date(2026, 3, 9), to_day=date(2026, 3, 9)
    )
    on_next_day = service.list_time_entries(
        session, employee, from_day=date(2026, 3, 10), to_day=date(2026, 3, 10)
    )

    assert [e.id for e in on_start_day] == [crossing.id]
    assert on_next_day == []


def test_list_includes_open_entries(session: Session, employee: User) -> None:
    open_entry = make_time_entry(session, employee, clock_in=at(8), duration=None)

    entries = service.list_time_entries(session, employee)

    assert [e.id for e in entries] == [open_entry.id]


def test_list_with_from_after_to_is_a_validation_error(session: Session, employee: User) -> None:
    with pytest.raises(ValidationFailed) as raised:
        service.list_time_entries(
            session, employee, from_day=date(2026, 3, 10), to_day=date(2026, 3, 9)
        )

    assert raised.value.code == ErrorCode.validation_error


def test_list_lets_a_manager_read_a_deactivated_employees_history(session: Session) -> None:
    manager = make_user(session, role=Role.manager)
    former = make_user(session, is_active=False)
    entry = make_time_entry(session, former)

    entries = service.list_time_entries(session, manager, user_id=former.id)

    assert [e.id for e in entries] == [entry.id]
