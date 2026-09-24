"""SEC-001 auth gate tests: session login, rate limit, API key strict mode."""

import pytest
from httpx import ASGITransport, AsyncClient

from garsync.api.auth import make_session_token, verify_session_token
from garsync.api.main import create_app

pytestmark = pytest.mark.integration

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

    # Adversarial review of specs/SEC-001 (2026-09-25, finding F2): the diff moved
    # five routes from `str` to `datetime.date`, and only two had a negative test.
    # These cover the other two, and they are parametrized over BOTH query params of
    # each route: an earlier draft sent `garbage` in one param only, so reverting the
    # other one to `str` still returned 422 and the test proved half of what it claimed.
    # `stats/heatmap` takes `int` year/month, which FastAPI validates on its own.
    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "url",
        [
            "/api/sleep?start_date=garbage&end_date=2026-01-01",
            "/api/sleep?start_date=2026-01-01&end_date=garbage",
            "/api/stats/summary?period=month&start_date=garbage",
            "/api/stats/summary?period=month&end_date=garbage",
        ],
    )
    async def test_garbage_date_returns_422_on_every_date_param(
        self, seeded_db, monkeypatch, url: str
    ) -> None:
        _app_env(monkeypatch, GARSYNC_API_KEY=API_KEY)
        headers = {"X-API-KEY": API_KEY}
        async with _client(create_app(conn=seeded_db)) as c:
            resp = await c.get(url, headers=headers)
        assert resp.status_code == 422


class TestNonAsciiInputDoesNotCrash:
    """[AC2/AC4] Auth checks answer 401/403 for any bytes a client can send.

    Adversarial review of specs/SEC-001 (2026-09-25, `agy/gemini-3.1-pro-high`,
    **Blocker**): `hmac.compare_digest` raises `TypeError: comparing strings with
    non-ASCII characters is not supported`, so a password, an `X-API-KEY` header or a
    session cookie carrying one non-ASCII character returned a 500 instead of a
    rejection — an unauthenticated crash on `/login`, and one that slipped past the
    rate limiter because it threw before the failure was recorded.

    The payloads are sent as **raw bytes** on purpose. A first draft used httpx's
    conveniences (`data={"password": "\u00f1"}`, `cookies.set`) and failed inside httpx
    with `UnicodeEncodeError` before any request existed — a test that looks like it
    exercises the server and does not. Percent-encoded UTF-8 in a form body and
    latin-1 bytes in a header or cookie are what a real client puts on the wire, and
    they are what reach these code paths.
    """

    @pytest.mark.anyio
    async def test_non_ascii_password_is_rejected_not_crashed(self, seeded_db, monkeypatch) -> None:
        """Unauthenticated: the login form is the only input needed."""
        _app_env(monkeypatch, GARSYNC_ACCESS_PASSWORD=PASSWORD)
        async with _client(create_app(conn=seeded_db)) as c:
            resp = await c.post(
                "/login",
                content=b"password=%C3%B1",  # percent-encoded UTF-8 "ñ"
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_failed_non_ascii_login_counts_towards_the_rate_limit(
        self, seeded_db, monkeypatch
    ) -> None:
        """The crash also bypassed the limiter: it threw before recording a failure."""
        _app_env(monkeypatch, GARSYNC_ACCESS_PASSWORD=PASSWORD)
        form = {"Content-Type": "application/x-www-form-urlencoded"}
        async with _client(create_app(conn=seeded_db)) as c:
            for _ in range(5):
                failed = await c.post("/login", content=b"password=%C3%B1", headers=form)
                assert failed.status_code == 401
            blocked = await c.post("/login", data={"password": PASSWORD})
        assert blocked.status_code == 429

    @pytest.mark.anyio
    async def test_non_ascii_api_key_is_rejected_not_crashed(self, seeded_db, monkeypatch) -> None:
        _app_env(monkeypatch, GARSYNC_API_KEY=API_KEY)
        async with _client(create_app(conn=seeded_db)) as c:
            resp = await c.get("/api/activities", headers={b"X-API-KEY": b"clave-\xf1"})
        assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_non_ascii_session_cookie_is_rejected_not_crashed(
        self, seeded_db, monkeypatch
    ) -> None:
        _app_env(monkeypatch, GARSYNC_ACCESS_PASSWORD=PASSWORD)
        async with _client(create_app(conn=seeded_db)) as c:
            raw_cookie = {b"Cookie": b"garsync_session=1800000000.\xf1"}
            page = await c.get("/", headers=raw_cookie)
            api = await c.get("/api/activities", headers=raw_cookie)
        assert page.status_code == 302  # redirected to /login
        assert api.status_code == 401

    @pytest.mark.anyio
    async def test_oversized_login_body_is_rejected_not_buffered(
        self, seeded_db, monkeypatch
    ) -> None:
        """The only unauthenticated write path does not buffer whatever arrives."""
        _app_env(monkeypatch, GARSYNC_ACCESS_PASSWORD=PASSWORD)
        async with _client(create_app(conn=seeded_db)) as c:
            resp = await c.post(
                "/login",
                content=b"password=" + b"A" * 200_000,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        assert resp.status_code == 401

    @pytest.mark.anyio
    async def test_undecodable_login_body_is_rejected_not_crashed(
        self, seeded_db, monkeypatch
    ) -> None:
        """A body that is not valid UTF-8 must not become an unhandled 500 either."""
        _app_env(monkeypatch, GARSYNC_ACCESS_PASSWORD=PASSWORD)
        async with _client(create_app(conn=seeded_db)) as c:
            resp = await c.post(
                "/login",
                content=b"password=\xff\xfe",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        assert resp.status_code == 401


class TestSessionTokenVerification:
    """[AC1/AC2] `verify_session_token` fails closed on every malformed shape.

    Adversarial review of specs/SEC-001 (2026-09-25, finding F3): the function has
    four failure branches and the suite only exercised the happy path and the
    no-cookie path, so a regression in token parsing would have gone unnoticed. The
    `now` parameter is injected rather than slept through, so expiry is tested without
    a slow or a flaky clock.
    """

    NOW = 1_800_000_000.0

    def test_valid_cookie_is_accepted(self) -> None:
        cookie = make_session_token(PASSWORD, now=self.NOW)
        assert verify_session_token(cookie, PASSWORD, now=self.NOW) is True

    @pytest.mark.parametrize("cookie", [None, "", "no-dot-at-all", "notanumber.abc"])
    def test_malformed_or_missing_cookie_is_rejected(self, cookie: str | None) -> None:
        assert verify_session_token(cookie, PASSWORD, now=self.NOW) is False

    def test_tampered_signature_is_rejected(self) -> None:
        expiry, signature = make_session_token(PASSWORD, now=self.NOW).split(".", 1)
        flipped = ("0" if signature[0] != "0" else "1") + signature[1:]
        assert verify_session_token(f"{expiry}.{flipped}", PASSWORD, now=self.NOW) is False

    def test_cookie_signed_with_another_password_is_rejected(self) -> None:
        cookie = make_session_token("another-password", now=self.NOW)
        assert verify_session_token(cookie, PASSWORD, now=self.NOW) is False

    def test_expired_cookie_is_rejected(self) -> None:
        cookie = make_session_token(PASSWORD, now=self.NOW)
        # The same cookie read after its expiry: the signature is still valid, only the
        # clock moved on. The future instant is bound to a name first — passing the
        # expression inline put `PASSWORD, <value>` on one line, which is the shape
        # gitleaks\' generic-api-key rule reads as an assignment (observed, 2026-09-25).
        after_expiry = self.NOW + 100_000_000
        assert verify_session_token(cookie, PASSWORD, now=after_expiry) is False

    def test_missing_access_password_is_rejected(self) -> None:
        cookie = make_session_token(PASSWORD, now=self.NOW)
        assert verify_session_token(cookie, "", now=self.NOW) is False
