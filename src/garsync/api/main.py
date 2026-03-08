"""FastAPI application factory for garsync."""

import os
import sqlite3
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from garsync.api.routes import activities, biometrics, sleep, stats, sync
from garsync.db.connection import get_connection
from garsync.db.schema import init_db


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

    # API Key Middleware
    # API Key Middleware
    api_key = os.environ.get("GARSYNC_API_KEY", "dev_key")

    @app.middleware("http")
    async def api_key_auth(request: Request, call_next: Any) -> Response:
        if request.url.path.startswith("/api/"):
            request_key = request.headers.get("X-API-KEY")
            if request_key != api_key:
                # Direct response for middleware
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Invalid or missing API Key"},
                )
        res: Response = await call_next(request)
        return res

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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
