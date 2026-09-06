"""SEC-001 auth gate tests: session login, rate limit, API key strict mode."""

import pytest
from httpx import ASGITransport, AsyncClient

from garsync.api.main import create_app

API_KEY = "test-api-key"
PASSWORD = "test-access-password"


def _app_env(monkeypatch: pytest.MonkeyPatch, **env: str | None) -> None:
    """Pin the auth env vars BEFORE create_app() reads them."""
    monkeypatch.delenv("GARSYNC_API_KEY", raising=False)
    monkeypatch.delenv("GARSYNC_ACCESS_PASSWORD", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def _client(app: object) -> AsyncClient:
    # https:// — the session cookie is Secure-flagged; httpx only sends it over https.
    return AsyncClient(transport=ASGITransport(app=app), base_url="https://test")


class TestApiKeyStrict:
    """[AC4] X-API-KEY: fail-closed, no dev_key fallback, 401 vs 403."""

    @pytest.mark.anyio
    async def test_missing_header_returns_401(self, seeded_db, monkeypatch) -> None:
        _app_env(monkeypatch, GARSYNC_API_KEY=API_KEY)
        async with _client(create_app(conn=seeded_db)) as c:
            resp = await c.get("/api/sync/status")
        assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_wrong_key_returns_403(self, seeded_db, monkeypatch) -> None:
        _app_env(monkeypatch, GARSYNC_API_KEY=API_KEY)
        async with _client(create_app(conn=seeded_db)) as c:
            resp = await c.get("/api/sync/status", headers={"X-API-KEY": "wrong"})
        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_valid_key_returns_200(self, seeded_db, monkeypatch) -> None:
        _app_env(monkeypatch, GARSYNC_API_KEY=API_KEY)
        async with _client(create_app(conn=seeded_db)) as c:
            resp = await c.get("/api/sync/status", headers={"X-API-KEY": API_KEY})
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_no_auth_env_open_with_warning(self, seeded_db, monkeypatch, caplog) -> None:
        _app_env(monkeypatch)  # both unset -> open mode
        async with _client(create_app(conn=seeded_db)) as c:
            resp = await c.get("/api/sync/status")
        assert resp.status_code == 200
        assert any("GARSYNC_ACCESS_PASSWORD" in r.message for r in caplog.records)


class TestSessionGate:
    """[AC1] Dashboard + /api/* behind the session cookie."""

    @pytest.fixture()
    async def password_client(self, seeded_db, monkeypatch):
        _app_env(monkeypatch, GARSYNC_ACCESS_PASSWORD=PASSWORD)
        return create_app(conn=seeded_db)

    @pytest.mark.anyio
    async def test_dashboard_redirects_to_login(self, password_client) -> None:
        async with _client(password_client) as c:
            resp = await c.get("/", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/login"

    @pytest.mark.anyio
    async def test_api_without_cookie_returns_401(self, password_client) -> None:
        async with _client(password_client) as c:
            resp = await c.get("/api/sync/status")
        assert resp.status_code == 401


class TestLoginFlow:
    """[AC2] POST /login issues a hardened cookie; logout clears it."""

    @pytest.fixture()
    async def password_client(self, seeded_db, monkeypatch):
        _app_env(monkeypatch, GARSYNC_ACCESS_PASSWORD=PASSWORD)
        return create_app(conn=seeded_db)

    @pytest.mark.anyio
    async def test_login_page_renders_without_error(self, password_client) -> None:
        async with _client(password_client) as c:
            resp = await c.get("/login")
        assert resp.status_code == 200
        assert "{{ERROR}}" not in resp.text
        assert 'action="/login"' in resp.text

    @pytest.mark.anyio
    async def test_correct_password_sets_cookie_and_grants_access(self, password_client) -> None:
        async with _client(password_client) as c:
            resp = await c.post("/login", data={"password": PASSWORD})
            assert resp.status_code == 303

            cookie = resp.headers["set-cookie"]
            assert "HttpOnly" in cookie
            assert "samesite=lax" in cookie.lower()
            assert "Secure" in cookie
            assert "garsync_session=" in cookie

            c.cookies.update(resp.cookies)
            granted = await c.get("/api/sync/status")
        assert granted.status_code == 200

    @pytest.mark.anyio
    async def test_wrong_password_renders_error(self, password_client) -> None:
        async with _client(password_client) as c:
            resp = await c.post("/login", data={"password": "nope"}, follow_redirects=False)
        assert resp.status_code == 401
        assert "Invalid password" in resp.text

    @pytest.mark.anyio
    async def test_logout_clears_access(self, password_client) -> None:
        async with _client(password_client) as c:
            await c.post("/login", data={"password": PASSWORD})
            resp = await c.post("/logout", follow_redirects=False)
            assert resp.status_code == 303

            revoked = await c.get("/api/sync/status")
        assert revoked.status_code == 401


class TestLoginRateLimit:
    """[AC3] 5 failures per 5 minutes -> 429."""

    @pytest.mark.anyio
    async def test_sixth_attempt_is_blocked(self, seeded_db, monkeypatch) -> None:
        _app_env(monkeypatch, GARSYNC_ACCESS_PASSWORD=PASSWORD)
        async with _client(create_app(conn=seeded_db)) as c:
            for _ in range(5):
                resp = await c.post("/login", data={"password": "nope"})
                assert resp.status_code == 401

            blocked = await c.post("/login", data={"password": PASSWORD})
            assert blocked.status_code == 429


class TestDateValidation:
    """[AC6] Malformed date params -> 422, never 500."""

    @pytest.mark.anyio
    async def test_biometrics_garbage_date_returns_422(self, seeded_db, monkeypatch) -> None:
        _app_env(monkeypatch, GARSYNC_API_KEY=API_KEY)
        headers = {"X-API-KEY": API_KEY}
        async with _client(create_app(conn=seeded_db)) as c:
            resp = await c.get(
                "/api/biometrics?start_date=garbage&end_date=2026-02-28", headers=headers
            )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_activities_garbage_date_returns_422(self, seeded_db, monkeypatch) -> None:
        _app_env(monkeypatch, GARSYNC_API_KEY=API_KEY)
        headers = {"X-API-KEY": API_KEY}
        async with _client(create_app(conn=seeded_db)) as c:
            resp = await c.get("/api/activities?start_date=nope", headers=headers)
        assert resp.status_code == 422
