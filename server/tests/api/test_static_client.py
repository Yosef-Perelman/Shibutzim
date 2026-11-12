"""Serving the built client from the API (plan 005): one container, one origin."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

INDEX_HTML = "<!doctype html><title>Shibutzim</title><div id=root></div>"


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    (site / "assets").mkdir(parents=True)
    (site / "index.html").write_text(INDEX_HTML)
    (site / "assets" / "app-abc123.js").write_text("console.log('app');")
    (site / "manifest.webmanifest").write_text('{"name": "Shibutzim"}')
    (site / "sw.js").write_text("self.skipWaiting();")
    (tmp_path / "secret.txt").write_text("do not serve")
    return site


@pytest.fixture
def site(static_dir: Path) -> TestClient:
    return TestClient(create_app(static_dir=static_dir), raise_server_exceptions=False)


# --- the single-page app ---


@pytest.mark.parametrize("path", ["/", "/login", "/me/shifts", "/manager/team"])
def test_an_app_address_returns_the_index_page(site: TestClient, path: str) -> None:
    response = site.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text == INDEX_HTML


@pytest.mark.parametrize("path", ["/", "/me/shifts", "/assets/app-abc123.js"])
def test_a_head_request_gets_the_headers_without_a_body(site: TestClient, path: str) -> None:
    response = site.head(path)

    assert response.status_code == 200
    assert response.content == b""


def test_the_index_page_is_never_cached(site: TestClient) -> None:
    response = site.get("/")

    assert response.headers["cache-control"] == "no-cache"


# --- files ---


def test_a_hashed_asset_is_served_and_cached_for_a_year(site: TestClient) -> None:
    response = site.get("/assets/app-abc123.js")

    assert response.status_code == 200
    assert response.text == "console.log('app');"
    assert "javascript" in response.headers["content-type"]
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_a_root_file_is_served_as_itself_and_not_cached(site: TestClient) -> None:
    manifest = site.get("/manifest.webmanifest")
    worker = site.get("/sw.js")

    assert manifest.json() == {"name": "Shibutzim"}
    assert manifest.headers["cache-control"] == "no-cache"
    assert worker.text == "self.skipWaiting();"
    assert worker.headers["cache-control"] == "no-cache"


def test_a_missing_file_is_a_404_and_not_the_index_page(site: TestClient) -> None:
    response = site.get("/assets/missing-def456.js")

    assert response.status_code == 404
    assert INDEX_HTML not in response.text


def test_a_path_outside_the_directory_is_not_served(site: TestClient) -> None:
    response = site.get("/..%2Fsecret.txt")

    assert "do not serve" not in response.text


# --- the API keeps its own behavior ---


def test_the_health_endpoint_is_still_json(site: TestClient) -> None:
    response = site.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_an_unknown_api_path_is_a_json_404_and_not_the_index_page(site: TestClient) -> None:
    response = site.get("/api/nope")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_an_api_endpoint_still_needs_a_token(site: TestClient) -> None:
    response = site.get("/api/users")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


# --- without a built client (development) ---


def test_without_the_directory_the_app_behaves_as_before(tmp_path: Path) -> None:
    client = TestClient(create_app(static_dir=tmp_path / "missing"), raise_server_exceptions=False)

    assert client.get("/").status_code == 404
    assert client.get("/api/health").json() == {"status": "ok"}
