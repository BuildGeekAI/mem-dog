"""FastAPI app: mounts health routes + MCP SSE at /mcp/."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.auth import set_api_key
from app.config import LOG_LEVEL
from app.health import router as health_router
from app.server import mcp

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="memdog MCP Server",
    description="MCP server exposing memdog data, search, and RAG tools over SSE",
    version="0.1.0",
)

app.include_router(health_router)


class McpAuthMiddleware:
    """Extract API key from SSE request headers/query and set it in contextvars."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            request = Request(scope)
            api_key = request.headers.get("x-api-key")
            if not api_key:
                api_key = request.query_params.get("api_key")
            set_api_key(api_key)
        await self.app(scope, receive, send)


# Mount the MCP SSE app at /mcp/ with auth middleware
mcp_sse_app = mcp.sse_app()
app.mount("/mcp", McpAuthMiddleware(mcp_sse_app))


if __name__ == "__main__":
    import uvicorn
    from app.config import PORT

    uvicorn.run(app, host="0.0.0.0", port=PORT)
