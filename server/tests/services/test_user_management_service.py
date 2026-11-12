"""Creating and deactivating users: managers only (plan 005, the Team screen)."""

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.errors import (
    Conflict,
    ErrorCode,
    Forbidden,
    NotFound,
    Unauthorized,
    ValidationFailed,
)
from app.core.security import verify_password
from app.models import User
from app.services import auth_service
from app.services import user_service as service
from tests.factories import NOW, make_user

NEW_PERSON = {
    "email": "noa.new@example.com",
    "name": "Noa New",
    "role": Role.employee,
    "hourly_rate": Decimal("42.50"),
    "password": "first-password-1",
}


# --- create: authorization ---


def test_create_user_is_for_managers_only(session: Session, employee: User) -> None:
    with pytest.raises(Forbidden):
        service.create_user(session, employee, **NEW_PERSON)


def test_create_user_by_an_employee_creates_nothing(
    session: Session, manager: User, employee: User
) -> None:
    with pytest.raises(Forbidden):
        service.create_user(session, employee, **NEW_PERSON)

    assert [user.name for user in service.list_users(session, manager)] == [
        "Eli Employee",
        "Mia Manager",
    ]


# --- create: happy path ---


def test_create_user_stores_the_person_with_the_given_fields(
    session: Session, manager: User
) -> None:
    user = service.create_user(session, manager, **NEW_PERSON)

    assert user.id is not None
    assert user.email == "noa.new@example.com"
    assert user.name == "Noa New"
    assert user.role is Role.employee
    assert user.hourly_rate == Decimal("42.50")
    assert user.is_active is True


def test_create_user_stores_a_hash_and_never_the_password(session: Session, manager: User) -> None:
    user = service.create_user(session, manager, **NEW_PERSON)

    assert user.password_hash != "first-password-1"
    assert verify_password("first-password-1", user.password_hash)


def test_create_user_lets_the_new_person_log_in(session: Session, manager: User) -> None:
    service.create_user(session, manager, **NEW_PERSON)

    token, user = auth_service.login(session, "noa.new@example.com", "first-password-1", now=NOW)

    assert token
    assert user.name == "Noa New"


def test_create_user_can_create_a_manager(session: Session, manager: User) -> None:
    user = service.create_user(session, manager, **{**NEW_PERSON, "role": Role.manager})

    assert user.role is Role.manager


def test_create_user_normalizes_the_email(session: Session, manager: User) -> None:
    user = service.create_user(
        session, manager, **{**NEW_PERSON, "email": "  Noa.New@Example.COM "}
    )

    assert user.email == "noa.new@example.com"


# --- create: rules ---


def test_create_user_with_an_existing_email_is_a_conflict(
    session: Session, manager: User, employee: User
) -> None:
    with pytest.raises(Conflict) as error:
        service.create_user(session, manager, **{**NEW_PERSON, "email": employee.email})

    assert error.value.code == ErrorCode.email_already_used


def test_create_user_matches_an_existing_email_in_any_case(
    session: Session, manager: User, employee: User
) -> None:
    with pytest.raises(Conflict) as error:
        service.create_user(session, manager, **{**NEW_PERSON, "email": employee.email.upper()})

    assert error.value.code == ErrorCode.email_already_used


def test_create_user_with_the_email_of_a_deactivated_user_is_a_conflict(
    session: Session, manager: User
) -> None:
    gone = make_user(session, is_active=False)

    with pytest.raises(Conflict):
        service.create_user(session, manager, **{**NEW_PERSON, "email": gone.email})


def test_a_failed_create_leaves_the_session_usable(session: Session, manager: User) -> None:
    with pytest.raises(Conflict):
        service.create_user(session, manager, **{**NEW_PERSON, "email": manager.email})

    assert service.create_user(session, manager, **NEW_PERSON).id is not None


# --- set active: authorization ---


def test_set_user_active_is_for_managers_only(
    session: Session, employee: User, other_employee: User
) -> None:
    with pytest.raises(Forbidden):
        service.set_user_active(session, employee, other_employee.id, is_active=False)


def test_set_user_active_by_an_employee_is_forbidden_even_for_a_missing_id(
    session: Session, employee: User
) -> None:
    with pytest.raises(Forbidden):
        service.set_user_active(session, employee, 999_999, is_active=False)


# --- set active: happy path and rules ---


def test_set_user_active_deactivates_a_person(
    session: Session, manager: User, employee: User
) -> None:
    user = service.set_user_active(session, manager, employee.id, is_active=False)

    assert user.id == employee.id
    assert user.is_active is False


def test_set_user_active_reactivates_a_person(session: Session, manager: User) -> None:
    gone = make_user(session, is_active=False)

    user = service.set_user_active(session, manager, gone.id, is_active=True)

    assert user.is_active is True


def test_set_user_active_to_the_current_value_changes_nothing(
    session: Session, manager: User, employee: User
) -> None:
    user = service.set_user_active(session, manager, employee.id, is_active=True)

    assert user.is_active is True


def test_set_user_active_for_a_missing_id_is_not_found(session: Session, manager: User) -> None:
    with pytest.raises(NotFound) as error:
        service.set_user_active(session, manager, 999_999, is_active=False)

    assert error.value.code == ErrorCode.user_not_found


def test_a_manager_cannot_deactivate_themself(session: Session, manager: User) -> None:
    with pytest.raises(ValidationFailed) as error:
        service.set_user_active(session, manager, manager.id, is_active=False)

    assert error.value.code == ErrorCode.cannot_deactivate_self
    assert manager.is_active is True


def test_a_manager_can_deactivate_another_manager(session: Session, manager: User) -> None:
    other = make_user(session, role=Role.manager)

    user = service.set_user_active(session, manager, other.id, is_active=False)

    assert user.is_active is False


# --- what deactivation means elsewhere ---


def test_a_deactivated_user_can_no_longer_log_in(
    session: Session, manager: User, employee: User
) -> None:
    service.set_user_active(session, manager, employee.id, is_active=False)

    with pytest.raises(Unauthorized) as error:
        auth_service.login(session, employee.email, "correct-horse-battery", now=NOW)

    assert error.value.code == ErrorCode.invalid_credentials


def test_a_deactivated_users_token_is_rejected(
    session: Session, manager: User, employee: User
) -> None:
    token, _ = auth_service.login(session, employee.email, "correct-horse-battery", now=NOW)
    service.set_user_active(session, manager, employee.id, is_active=False)

    with pytest.raises(Unauthorized) as error:
        auth_service.authenticate_token(session, token, now=NOW)

    assert error.value.code == ErrorCode.invalid_token


def test_a_deactivated_employee_is_not_found_by_name(
    session: Session, manager: User, employee: User
) -> None:
    service.set_user_active(session, manager, employee.id, is_active=False)

    with pytest.raises(ValidationFailed) as error:
        service.find_active_employee(session, manager, "Eli")

    assert error.value.code == ErrorCode.user_not_assignable
