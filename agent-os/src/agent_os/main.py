"""Agent OS application entry point."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from agent_os.config import load_settings
from agent_os.db.connection import get_session, init_db
from agent_os.observability.logging import setup_logging
from agent_os.observability.tracing import setup_tracing


class DbSessionMiddleware(BaseHTTPMiddleware):
    """为每个请求创建独立的 DB session，注入到 request.state。"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        async for session in get_session():
            request.state.db_session = session
            response = await call_next(request)
            return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = load_settings()
    setup_logging(settings.observability.logging)
    setup_tracing(settings.observability.tracing)
    await init_db(settings.database)
    yield


def create_app() -> FastAPI:
    settings = load_settings()

    app = FastAPI(
        title="Agent OS",
        version="0.1.0",
        lifespan=lifespan,
    )

    # API 路由
    from agent_os.api.tasks import router as tasks_router
    app.include_router(tasks_router, prefix="/api/v1")

    # 中间件（注意顺序：后添加的先执行）
    from agent_os.gateway.middleware import RateLimitMiddleware, TenantMiddleware
    app.add_middleware(DbSessionMiddleware)
    app.add_middleware(RateLimitMiddleware, settings=settings.gateway)
    app.add_middleware(TenantMiddleware)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
