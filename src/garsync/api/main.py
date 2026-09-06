"""FastAPI application factory for garsync."""

import hmac
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
    make_session_token,
    render_login_page,
    verify_session_token,
)
from garsync.api.routes import activities, biometrics, sleep, stats, sync
from garsync.db.connection import get_connection
from garsync.db.schema import init_db

logger = logging.getLogger("garsync.auth")


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
                    if hmac.compare_digest(provided, api_key):
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

        form = parse_qs((await request.body()).decode())
        supplied = form.get("password", [""])[0]

        if access_password and hmac.compare_digest(supplied, access_password):
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
