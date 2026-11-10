"""Authorization helpers used by every service (coding-rules: services decide)."""

import pytest

from app.core.errors import ErrorCode, Forbidden
from app.models import User
from app.services.authorization import ensure_manager, ensure_self_or_manager


def test_ensure_manager_allows_a_manager(manager: User) -> None:
    ensure_manager(manager)


def test_ensure_manager_rejects_an_employee(employee: User) -> None:
    with pytest.raises(Forbidden) as raised:
        ensure_manager(employee)

    assert raised.value.code == ErrorCode.forbidden


def test_ensure_self_or_manager_allows_the_employee_themselves(employee: User) -> None:
    ensure_self_or_manager(employee, employee.id)


def test_ensure_self_or_manager_allows_a_manager_for_anyone(manager: User, employee: User) -> None:
    ensure_self_or_manager(manager, employee.id)


def test_ensure_self_or_manager_rejects_an_employee_for_someone_else(
    employee: User, other_employee: User
) -> None:
    with pytest.raises(Forbidden) as raised:
        ensure_self_or_manager(employee, other_employee.id)

    assert raised.value.code == ErrorCode.forbidden
