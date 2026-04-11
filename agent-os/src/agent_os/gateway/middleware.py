"""Gateway middleware — auth, rate limiting, tenant isolation."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from agent_os.config import GatewaySettings


class TenantMiddleware(BaseHTTPMiddleware):
    """提取并校验租户信息。MVP 从 header 中获取，后续对接认证系统。"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        tenant_id = request.headers.get("X-Tenant-ID", "default")
        user_id = request.headers.get("X-User-ID", "anonymous")
        request.state.tenant_id = tenant_id
        request.state.user_id = user_id
        response = await call_next(request)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """简易租户级限流。MVP 使用内存计数器，后续迁移至 Redis。"""

    def __init__(self, app, settings: GatewaySettings | None = None):
        super().__init__(app)
        self.settings = settings or GatewaySettings()
        self._counts: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        tenant_id = getattr(request.state, "tenant_id", "default")
        now = time.monotonic()
        window = self._counts[tenant_id]
        window[:] = [t for t in window if now - t < 60]
        if len(window) >= self.settings.rate_limit_per_tenant:
            return Response(status_code=429, content="Rate limit exceeded")
        window.append(now)
        return await call_next(request)
