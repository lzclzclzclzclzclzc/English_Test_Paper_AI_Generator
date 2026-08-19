from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .db import init_db
from .errors import register_error_handlers
from .routes import dev_router, router
from .admin_routes import admin_router


@asynccontextmanager
async def _lifespan(_: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="墨卷支付服务",
        docs_url="/payapi/docs",
        openapi_url="/payapi/openapi.json",
        lifespan=_lifespan,
    )
    register_error_handlers(app)
    app.include_router(router)
    app.include_router(admin_router)
    if get_settings().mock_pay:
        app.include_router(dev_router)

    @app.get("/payapi/health")
    def health() -> dict:
        # Lightweight liveness echo for cross-service probes (admin /system/health).
        return {"status": "ok"}

    return app


app = create_app()
