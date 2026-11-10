"""GET /api/pay and GET /api/pay/team: shape, status codes and the 401 / 403 matrix."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User
from tests.factories import make_time_entry

PAY = "/api/pay"
TEAM = "/api/pay/team"
MARCH_9 = {"from": "2026-03-09", "to": "2026-03-09"}
HOUR = timedelta(hours=1)


def utc(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 3, day, hour, minute, tzinfo=UTC)


def error_code(response) -> str:
    return response.json()["error"]["code"]


# --- authentication ---


@pytest.mark.parametrize("path", [PAY, TEAM], ids=["pay", "team"])
def test_endpoint_without_a_token_returns_401(client: TestClient, path: str) -> None:
    response = client.get(path, params=MARCH_9)

    assert response.status_code == 401
    assert error_code(response) == "invalid_token"


# --- GET /api/pay ---


def test_pay_returns_the_breakdown_per_day_and_tier(
    employee_client: TestClient, session: Session, employee: User
) -> None:
    make_time_entry(session, employee, clock_in=utc(9, 5), duration=9 * HOUR)  # 07:00-16:00 local

    response = employee_client.get(PAY, params=MARCH_9)

    assert response.status_code == 200
    assert response.json() == {
        "user_id": employee.id,
        "from": "2026-03-09",
        "to": "2026-03-09",
        "days": [
            {
                "work_day": "2026-03-09",
                "seconds": 32400,
                "hours": "9.00",
                "amount": "462.50",
                "lines": [
                    {
                        "from_hour": "0",
                        "to_hour": "8",
                        "multiplier": "1.00",
                        "seconds": 28800,
                        "hours": "8.00",
                        "amount": "400.00",
                    },
                    {
                        "from_hour": "8",
                        "to_hour": "10",
                        "multiplier": "1.25",
                        "seconds": 3600,
                        "hours": "1.00",
                        "amount": "62.50",
                    },
                ],
            }
        ],
        "seconds": 32400,
        "hours": "9.00",
        "amount": "462.50",
        "open_entries": 0,
    }


def test_pay_open_ended_tier_has_a_null_upper_bound(
    employee_client: TestClient, session: Session, employee: User
) -> None:
    make_time_entry(session, employee, clock_in=utc(9, 4), duration=12 * HOUR)

    lines = employee_client.get(PAY, params=MARCH_9).json()["days"][0]["lines"]

    assert lines[-1]["to_hour"] is None
    assert lines[-1]["multiplier"] == "1.50"


def test_pay_shows_hours_for_display_and_exact_seconds(
    employee_client: TestClient, session: Session, employee: User
) -> None:
    make_time_entry(session, employee, clock_in=utc(9, 5), duration=8 * HOUR + timedelta(minutes=1))

    day = employee_client.get(PAY, params=MARCH_9).json()["days"][0]

    assert (day["seconds"], day["hours"]) == (28860, "8.02")


def test_pay_reports_open_entries_separately(
    employee_client: TestClient, session: Session, employee: User
) -> None:
    make_time_entry(session, employee, clock_in=utc(9, 5), duration=None)

    body = employee_client.get(PAY, params=MARCH_9).json()

    assert body["open_entries"] == 1
    assert body["amount"] == "0.00"
    assert body["days"] == []


def test_pay_of_another_user_as_manager(
    manager_client: TestClient, session: Session, employee: User
) -> None:
    make_time_entry(session, employee, clock_in=utc(9, 5), duration=8 * HOUR)

    response = manager_client.get(PAY, params={"user_id": employee.id, **MARCH_9})

    assert response.status_code == 200
    assert (response.json()["user_id"], response.json()["amount"]) == (employee.id, "400.00")


def test_pay_naming_yourself_is_allowed(employee_client: TestClient, employee: User) -> None:
    response = employee_client.get(PAY, params={"user_id": employee.id, **MARCH_9})

    assert response.status_code == 200


def test_pay_of_another_user_as_employee_returns_403(
    employee_client: TestClient, other_employee: User
) -> None:
    response = employee_client.get(PAY, params={"user_id": other_employee.id, **MARCH_9})

    assert response.status_code == 403
    assert response.json() == {
        "error": {"code": "forbidden", "message": "You may only access your own data."}
    }


def test_pay_of_an_unknown_user_as_manager_returns_404(manager_client: TestClient) -> None:
    response = manager_client.get(PAY, params={"user_id": 999_999, **MARCH_9})

    assert response.status_code == 404
    assert error_code(response) == "user_not_found"


@pytest.mark.parametrize(
    "params",
    [{}, {"from": "2026-03-09"}, {"to": "2026-03-09"}, {"from": "soon", "to": "later"}],
    ids=["nothing", "no_to", "no_from", "malformed"],
)
def test_pay_without_a_valid_range_returns_422(employee_client: TestClient, params: dict) -> None:
    response = employee_client.get(PAY, params=params)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_pay_with_from_after_to_returns_422(employee_client: TestClient) -> None:
    response = employee_client.get(PAY, params={"from": "2026-03-10", "to": "2026-03-09"})

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


# --- GET /api/pay/team ---


def test_team_pay_returns_a_row_per_user_and_totals(
    manager_client: TestClient,
    session: Session,
    employee: User,
    other_employee: User,
    manager: User,
) -> None:
    make_time_entry(session, employee, clock_in=utc(9, 5), duration=8 * HOUR)
    make_time_entry(session, other_employee, clock_in=utc(9, 5), duration=9 * HOUR)

    response = manager_client.get(TEAM, params=MARCH_9)

    assert response.status_code == 200
    body = response.json()
    assert (body["from"], body["to"]) == ("2026-03-09", "2026-03-09")
    assert [row["name"] for row in body["users"]] == ["Dana Other", "Eli Employee", "Mia Manager"]
    assert body["users"][0] == {
        "user_id": other_employee.id,
        "name": "Dana Other",
        "role": "employee",
        "hourly_rate": "50.00",
        "seconds": 32400,
        "hours": "9.00",
        "amount": "462.50",
        "open_entries": 0,
    }
    assert (body["seconds"], body["hours"], body["amount"]) == (61200, "17.00", "862.50")


def test_team_pay_as_employee_returns_403(employee_client: TestClient) -> None:
    response = employee_client.get(TEAM, params=MARCH_9)

    assert response.status_code == 403
    assert error_code(response) == "forbidden"


def test_team_pay_without_a_range_returns_422(manager_client: TestClient) -> None:
    response = manager_client.get(TEAM)

    assert response.status_code == 422
    assert error_code(response) == "validation_error"


def test_team_pay_with_from_after_to_returns_422(manager_client: TestClient) -> None:
    response = manager_client.get(TEAM, params={"from": "2026-03-10", "to": "2026-03-09"})

    assert response.status_code == 422
    assert error_code(response) == "validation_error"
