"""Shared fixtures.

Database tests run against `shibutzim_test` (never the development database). The schema is
migrated once per session, and each test runs in a transaction that is rolled back afterwards. The
session uses savepoints, so services may call `commit()` without leaking data between tests.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.enums import Role
from app.db import get_session
from app.deps import get_now
from app.main import app
from app.models import User
from tests.factories import NOW, auth_headers, make_user

SERVER_DIR = Path(__file__).resolve().parents[1]
DB_UNREACHABLE = "Database not reachable – run `docker compose up -d db` (then retry): {error}"


def alembic_config(url: str) -> Config:
    config = Config(str(SERVER_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(SERVER_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def database_error(engine: Engine) -> str | None:
    """None if the database answers, else the first line of the connection error."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError as error:
        return str(error).splitlines()[0]
    return None


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = get_settings().test_database_url
    database = make_url(url).database or ""
    # The schema is rebuilt from scratch below, so never touch a database that is not a test one.
    if not database.endswith("_test"):
        pytest.exit(
            f"Refusing to run: TEST_DATABASE_URL points at '{database}', not a *_test database."
        )

    test_engine = create_engine(url, pool_pre_ping=True)
    unreachable = database_error(test_engine)
    if unreachable:
        test_engine.dispose()
        pytest.fail(DB_UNREACHABLE.format(error=unreachable), pytrace=False)

    config = alembic_config(url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    connection = engine.connect()
    outer = connection.begin()
    db_session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        autoflush=False,
        expire_on_commit=False,
    )
    try:
        yield db_session
    finally:
        db_session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def api(session: Session) -> Iterator[None]:
    """Route the app to the per-test session and freeze its clock at NOW."""

    def override_get_session() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_now] = lambda: NOW
    try:
        yield
    finally:
        app.dependency_overrides.clear()


def api_client(user: User | None = None) -> TestClient:
    headers = auth_headers(user) if user else None
    return TestClient(app, raise_server_exceptions=False, headers=headers)


@pytest.fixture
def client(api: None) -> TestClient:
    """An unauthenticated API client."""
    return api_client()


@pytest.fixture
def manager_client(api: None, manager: User) -> TestClient:
    return api_client(manager)


@pytest.fixture
def employee_client(api: None, employee: User) -> TestClient:
    return api_client(employee)


@pytest.fixture
def other_employee_client(api: None, other_employee: User) -> TestClient:
    return api_client(other_employee)


@pytest.fixture
def manager(session: Session) -> User:
    return make_user(session, role=Role.manager, name="Mia Manager")


@pytest.fixture
def employee(session: Session) -> User:
    return make_user(session, role=Role.employee, name="Eli Employee")


@pytest.fixture
def other_employee(session: Session) -> User:
    return make_user(session, role=Role.employee, name="Dana Other")
