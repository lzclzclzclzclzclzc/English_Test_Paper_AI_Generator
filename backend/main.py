from __future__ import annotations

import logging
import time
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api import attempts, health, mastery, papers, solutions
from backend.auth import routes as auth_routes
from backend.errors import BackendError, backend_error_response, install_error_handlers
from shared.config import get_config
from shared import storage

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    config = get_config().backend
    app = FastAPI(title="English Test Paper AI Generator Backend")
    install_error_handlers(app)

    if config.env == "development":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def request_logger(request: Request, call_next):
        trace_id = uuid4().hex
        request.state.trace_id = trace_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.exception("Unhandled backend error")
            response = backend_error_response(BackendError(str(exc)), request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Trace-Id"] = trace_id
        logger.info("%s %s %s %.2fms trace=%s", request.method, request.url.path, response.status_code, duration_ms, trace_id)
        return response

    storage.init_db()
    app.include_router(health.router, prefix="/api")
    app.include_router(auth_routes.router, prefix="/api")
    app.include_router(papers.router, prefix="/api")
    app.include_router(solutions.router, prefix="/api")
    app.include_router(attempts.router, prefix="/api")
    app.include_router(mastery.router, prefix="/api")

    if config.env == "test":
        from backend.api import _test

        app.include_router(_test.router, prefix="/api/test")

    static_dir = Path(config.static_dir)
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    return app


app = create_app()
