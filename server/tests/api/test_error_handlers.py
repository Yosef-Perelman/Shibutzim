"""Every non-2xx response has one shape: {"error": {"code", "message"[, "details"]}}."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import (
    Conflict,
    DomainError,
    ErrorCode,
    Forbidden,
    NotFound,
    Unauthorized,
    ValidationFailed,
)
from app.main import create_app


class Payload(BaseModel):
    hours: int


def make_client(error: Exception | None = None) -> TestClient:
    test_app: FastAPI = create_app()

    @test_app.get("/raise")
    def raise_error() -> None:
        assert error is not None
        raise error

    @test_app.post("/validate")
    def validate(payload: Payload) -> dict[str, int]:
        return {"hours": payload.hours}

    return TestClient(test_app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (ValidationFailed(ErrorCode.entry_too_long, "An entry may not exceed 24 hours."), 422),
        (Unauthorized(ErrorCode.invalid_credentials, "Wrong email or password."), 401),
        (Forbidden(ErrorCode.forbidden, "Managers only."), 403),
        (NotFound(ErrorCode.user_not_found, "No user 42."), 404),
        (Conflict(ErrorCode.already_clocked_in, "You already have an open entry."), 409),
    ],
    ids=["validation_failed", "unauthorized", "forbidden", "not_found", "conflict"],
)
def test_domain_error_maps_to_status_and_shape(error: DomainError, status: int) -> None:
    response = make_client(error).get("/raise")

    assert response.status_code == status
    assert response.json() == {"error": {"code": error.code, "message": error.message}}


def test_unauthorized_sets_www_authenticate_header() -> None:
    response = make_client(Unauthorized(ErrorCode.token_expired, "Token expired.")).get("/raise")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_domain_error_default_code_is_its_class_default() -> None:
    response = make_client(Forbidden()).get("/raise")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_domain_error_details_are_included_when_given() -> None:
    error = ValidationFailed(ErrorCode.validation_error, "Bad input.", details={"field": "hours"})

    response = make_client(error).get("/raise")

    assert response.json()["error"]["details"] == {"field": "hours"}


def test_request_validation_error_uses_the_same_shape() -> None:
    response = make_client().post("/validate", json={"hours": "many"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"]
    assert body["error"]["details"]["errors"][0]["loc"] == ["body", "hours"]


def test_unexpected_exception_becomes_internal_error_without_details() -> None:
    response = make_client(RuntimeError("secret database password")).get("/raise")

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Something went wrong on our side."}
    }
    assert "secret" not in response.text
