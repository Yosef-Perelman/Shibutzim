"""The MCP server's start-up check: a wrong token stops it before any client connects."""

from contextlib import nullcontext

import pytest
from sqlalchemy.orm import Session

from app.core.errors import Unauthorized
from app.mcp.__main__ import check_token
from app.models import User
from app.services import user_service
from tests.factories import NOW
from tests.services.test_mcp_server import token_of


def test_the_check_names_the_user_and_the_role(session: Session, employee: User) -> None:
    described = check_token(lambda: nullcontext(session), token_of(employee), now=NOW)

    assert described == "Eli Employee (employee)"


def test_the_check_rejects_a_garbage_token(session: Session) -> None:
    with pytest.raises(Unauthorized):
        check_token(lambda: nullcontext(session), "not-a-token", now=NOW)


def test_the_check_rejects_the_token_of_a_deactivated_user(
    session: Session, manager: User, employee: User
) -> None:
    token = token_of(employee)
    user_service.set_user_active(session, manager, employee.id, is_active=False)

    with pytest.raises(Unauthorized):
        check_token(lambda: nullcontext(session), token, now=NOW)
