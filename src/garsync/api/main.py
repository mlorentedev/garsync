"""FastAPI application factory for garsync."""

import logging
import os
import sqlite3
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from garsync.api.auth import (
    SESSION_COOKIE_NAME,
    SESSION_TTL_SECONDS,
    LoginRateLimiter,
    constant_time_equals,
    make_session_token,
    render_login_page,
    verify_session_token,
)
from garsync.api.routes import activities, biometrics, sleep, stats, sync
from garsync.db.connection import get_connection
from garsync.db.schema import init_db

logger = logging.getLogger("garsync.auth")

# Largest login body the app will buffer before treating the attempt as failed. The
# URL-encoded form is a handful of bytes; anything past this is a client trying to spend
# the server's memory, and the endpoint needs no credentials to reach it.
MAX_LOGIN_BODY_BYTES = 4096


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage database connection lifecycle."""
    db_path = os.environ.get("GARSYNC_DB_PATH", "data/garsync.db")
    conn = get_connection(db_path)
    init_db(conn)
    app.state.db = conn
    yield
    conn.close()


def create_app(conn: sqlite3.Connection | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        conn: Optional pre-configured connection (for testing).
             If provided, lifespan is skipped.
    """
    if conn is not None:
        app = FastAPI(title="GarSync API", version="0.1.0")
        app.state.db = conn
    else:
        app = FastAPI(title="GarSync API", version="0.1.0", lifespan=lifespan)

    access_password = os.environ.get("GARSYNC_ACCESS_PASSWORD")
    api_key = os.environ.get("GARSYNC_API_KEY")
    auth_active = bool(access_password or api_key)
    insecure_cookies = os.environ.get("GARSYNC_INSECURE_COOKIES") == "1"
    limiter = LoginRateLimiter()

    if not auth_active:
        logger.warning(
            "Auth is DISABLED: neither GARSYNC_ACCESS_PASSWORD nor GARSYNC_API_KEY "
            "is set. The API and dashboard are UNPROTECTED. This is only acceptable "
            "on a trusted local network."
        )
    elif not access_password:
        logger.warning(
            "Dashboard is UNAUTHENTICATED: GARSYNC_ACCESS_PASSWORD is not set. "
            "Only /api/* requires the API key. Set GARSYNC_ACCESS_PASSWORD before "
            "deploying publicly."
        )

    @app.middleware("http")
    async def auth_gate(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """SEC-001 gate: session cookie for pages, session-or-API-key for /api/*.

        401 = no credentials presented; 403 = credentials presented but invalid.
        """
        if not auth_active:
            return await call_next(request)

        path = request.url.path
        if path in ("/login", "/logout"):
            return await call_next(request)

        if path.startswith("/api/"):
            if api_key:
                provided = request.headers.get("X-API-KEY")
                if provided is not None:
                    if constant_time_equals(provided, api_key):
                        return await call_next(request)
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "Invalid API key"},
                    )
            if access_password and verify_session_token(
                request.cookies.get(SESSION_COOKIE_NAME), access_password
            ):
                return await call_next(request)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication required"},
            )

        if access_password:
            if verify_session_token(request.cookies.get(SESSION_COOKIE_NAME), access_password):
                return await call_next(request)
            return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

        return await call_next(request)

    @app.get("/login", include_in_schema=False)
    async def login_page(request: Request) -> Response:
        error = "Invalid password. Try again." if "error" in request.query_params else ""
        return HTMLResponse(render_login_page(error))

    @app.post("/login", include_in_schema=False)
    async def login_submit(request: Request) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        if limiter.is_blocked(client_ip):
            return HTMLResponse(
                render_login_page("Too many failed attempts. Try again later."),
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Cap what an unauthenticated endpoint will buffer: `await request.body()` read
        # whatever the client sent, so `POST /login` was a free memory lever for anyone
        # who could reach it. The proxy's body limit is a second line of defence, not the
        # first one on the app's only unauthenticated write path. Independent review of
        # specs/SEC-001 (2026-09-25) raised it as speculative; it is cheap to close, and an
        # oversized body counts as a failed attempt rather than a distinct status, so the
        # response is not an oracle for how the body was rejected.
        #
        # This cap holds only while nothing upstream has consumed the body: FastAPI does not
        # parse one for a handler that declares no body parameter, and the auth middleware
        # never reads it, so the request arrives unconsumed (verified: `_stream_consumed` is
        # False at entry and the loop receives chunks). If a future middleware starts reading
        # the body, the proxy's size limit is the remaining backstop.
        body = b""
        async for chunk in request.stream():
            body += chunk
            if len(body) > MAX_LOGIN_BODY_BYTES:
                limiter.record_failure(client_ip)
                return HTMLResponse(
                    render_login_page("Invalid password. Try again."),
                    status_code=status.HTTP_401_UNAUTHORIZED,
                )

        # errors="replace": a body that is not valid UTF-8 is a wrong password, not a
        # 500. A bare `.decode()` raised UnicodeDecodeError on `password=\xff` —
        # reachable unauthenticated, and the same crash class the compare fix addresses.
        form = parse_qs(body.decode("utf-8", errors="replace"))
        supplied = form.get("password", [""])[0]

        if access_password and constant_time_equals(supplied, access_password):
            limiter.reset(client_ip)
            response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
            response.set_cookie(
                SESSION_COOKIE_NAME,
                make_session_token(access_password),
                max_age=SESSION_TTL_SECONDS,
                httponly=True,
                samesite="lax",
                secure=not insecure_cookies,
            )
            return response

        limiter.record_failure(client_ip)
        return HTMLResponse(
            render_login_page("Invalid password. Try again."),
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    @app.post("/logout", include_in_schema=False)
    async def logout() -> Response:
        response = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(SESSION_COOKIE_NAME)
        return response

    allowed_origins = [
        origin.strip()
        for origin in os.environ.get("GARSYNC_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    ]
    if "*" in allowed_origins:
        msg = (
            "GARSYNC_ALLOWED_ORIGINS must list explicit origins; '*' is not allowed "
            "because the API uses credentialed (cookie / X-API-KEY) requests."
        )
        raise ValueError(msg)
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["X-API-KEY", "Content-Type"],
        )

    app.include_router(activities.router)
    app.include_router(biometrics.router)
    app.include_router(sleep.router)
    app.include_router(stats.router)
    app.include_router(sync.router)

    static_dir = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


app = create_app()
