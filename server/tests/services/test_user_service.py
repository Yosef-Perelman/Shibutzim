"""User listing: managers only, filters and ordering (plan 003: the board's employee picker)."""

import pytest
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.errors import ErrorCode, Forbidden, ValidationFailed
from app.models import User
from app.services import user_service as service
from tests.factories import make_user


def names(users: list[User]) -> list[str]:
    return [user.name for user in users]


# --- authorization ---


def test_list_users_is_for_managers_only(session: Session, employee: User) -> None:
    with pytest.raises(Forbidden):
        service.list_users(session, employee)


# --- listing ---


def test_list_users_returns_everyone_ordered_by_name(
    session: Session, manager: User, employee: User, other_employee: User
) -> None:
    users = service.list_users(session, manager)

    assert names(users) == ["Dana Other", "Eli Employee", "Mia Manager"]


def test_list_users_filters_by_role(
    session: Session, manager: User, employee: User, other_employee: User
) -> None:
    users = service.list_users(session, manager, role=Role.employee)

    assert names(users) == ["Dana Other", "Eli Employee"]


def test_list_users_filters_by_active_state(
    session: Session, manager: User, employee: User
) -> None:
    make_user(session, name="Aaron Gone", is_active=False)

    assert names(service.list_users(session, manager, is_active=True)) == [
        "Eli Employee",
        "Mia Manager",
    ]
    assert names(service.list_users(session, manager, is_active=False)) == ["Aaron Gone"]


def test_list_users_combines_the_filters(session: Session, manager: User, employee: User) -> None:
    make_user(session, name="Aaron Gone", is_active=False)
    make_user(session, name="Zed Gone Manager", role=Role.manager, is_active=False)

    users = service.list_users(session, manager, role=Role.employee, is_active=False)

    assert names(users) == ["Aaron Gone"]


def test_list_users_with_no_match_returns_an_empty_list(session: Session, manager: User) -> None:
    assert service.list_users(session, manager, role=Role.employee) == []


def test_list_users_breaks_a_name_tie_by_id(session: Session, manager: User) -> None:
    first = make_user(session, name="Same Name")
    second = make_user(session, name="Same Name")

    users = service.list_users(session, manager, role=Role.employee)

    assert [user.id for user in users] == [first.id, second.id]


# --- finding an employee by the name a manager says ---


def test_find_active_employee_is_for_managers_only(session: Session, employee: User) -> None:
    with pytest.raises(Forbidden):
        service.find_active_employee(session, employee, "Eli")


def test_find_active_employee_matches_a_first_name_in_any_case(
    session: Session, manager: User, employee: User
) -> None:
    assert service.find_active_employee(session, manager, "  eLi ") == employee


def test_find_active_employee_prefers_the_full_name(session: Session, manager: User) -> None:
    make_user(session, name="Eli Adler")
    second = make_user(session, name="Eli Second")

    assert service.find_active_employee(session, manager, "eli second") == second


def test_find_active_employee_ignores_managers_and_deactivated_people(
    session: Session, manager: User
) -> None:
    make_user(session, name="Gone Person", is_active=False)

    for name in ("Mia", "Gone"):
        with pytest.raises(ValidationFailed) as raised:
            service.find_active_employee(session, manager, name)
        assert raised.value.code == ErrorCode.user_not_assignable


def test_find_active_employee_lists_the_candidates_when_the_name_is_ambiguous(
    session: Session, manager: User
) -> None:
    make_user(session, name="Dana Levi")
    make_user(session, name="Dana Katz")

    with pytest.raises(ValidationFailed) as raised:
        service.find_active_employee(session, manager, "Dana")

    assert "Dana Katz, Dana Levi" in raised.value.message
