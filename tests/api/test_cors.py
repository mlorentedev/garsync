"""SEC-001 CORS tests: allowlist via GARSYNC_ALLOWED_ORIGINS, wildcard impossible."""

import pytest
from httpx import ASGITransport, AsyncClient

from garsync.api.main import create_app

API_KEY = "test-api-key"


def _client(app: object) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _preflight_headers(origin: str) -> dict[str, str]:
    return {"Origin": origin, "Access-Control-Request-Method": "GET"}


@pytest.mark.anyio
async def test_cors_disabled_when_env_unset(seeded_db, monkeypatch) -> None:
    monkeypatch.delenv("GARSYNC_ALLOWED_ORIGINS", raising=False)
    monkeypatch.setenv("GARSYNC_API_KEY", API_KEY)
    async with _client(create_app(conn=seeded_db)) as c:
        resp = await c.options(
            "/api/sync/status",
            headers=_preflight_headers("https://anywhere.example"),
        )
    assert "access-control-allow-origin" not in resp.headers


@pytest.mark.anyio
async def test_cors_allowlisted_origin_is_echoed(seeded_db, monkeypatch) -> None:
    monkeypatch.setenv("GARSYNC_API_KEY", API_KEY)
    monkeypatch.setenv("GARSYNC_ALLOWED_ORIGINS", "https://good.example")
    async with _client(create_app(conn=seeded_db)) as c:
        resp = await c.options(
            "/api/sync/status",
            headers=_preflight_headers("https://good.example"),
        )
    assert resp.headers["access-control-allow-origin"] == "https://good.example"


@pytest.mark.anyio
async def test_cors_non_allowlisted_origin_is_denied(seeded_db, monkeypatch) -> None:
    monkeypatch.setenv("GARSYNC_API_KEY", API_KEY)
    monkeypatch.setenv("GARSYNC_ALLOWED_ORIGINS", "https://good.example")
    async with _client(create_app(conn=seeded_db)) as c:
        resp = await c.options(
            "/api/sync/status",
            headers=_preflight_headers("https://evil.example"),
        )
    assert resp.headers.get("access-control-allow-origin") != "https://evil.example"


def test_cors_wildcard_origin_is_rejected_at_startup(seeded_db, monkeypatch) -> None:
    """AC5: '*' must never be honored with credentials, so it fails closed at create_app()."""
    monkeypatch.setenv("GARSYNC_API_KEY", API_KEY)
    monkeypatch.setenv("GARSYNC_ALLOWED_ORIGINS", "https://ok.example, *")
    with pytest.raises(ValueError, match="explicit origins"):
        create_app()
