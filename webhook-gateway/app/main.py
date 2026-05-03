"""Webhook Gateway — FastAPI application entry point.

Receives inbound channel webhooks (email, video conferencing, generic),
normalises them into UniversalEnvelope format, and forwards them through
the existing memdog webhook pipeline.  Provides OTEL tracing, Gemini 3
Flash integration for message understanding, and proxy endpoints for
laptop / UI access.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .routers import api_proxy, channels, chat_ui, health, integration_proxy, providers, query, webhooks
from .telemetry import setup_otel

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
)

setup_otel()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if config.ZOOM_WS_ENABLED:
        from .zoom_ws import zoom_ws_client
        await zoom_ws_client.start()
    yield
    if config.ZOOM_WS_ENABLED:
        from .zoom_ws import zoom_ws_client
        await zoom_ws_client.stop()


app = FastAPI(
    title="Webhook Gateway",
    version="0.1.0",
    description=(
        "Channel adapter, integration proxy, and webhook forwarder for the memdog platform. "
        "Accepts inbound messages from 25+ channels, normalises them into UniversalEnvelope "
        "format, and forwards through the webhook pipeline. Provides a credential-injecting "
        "API proxy for 300+ integration providers with per-provider rate limiting and "
        "unified data model transforms."
    ),
    lifespan=lifespan,
    openapi_tags=[
        {"name": "health", "description": "Health and readiness probes"},
        {"name": "webhooks", "description": "Inbound webhook receivers for all channel types"},
        {"name": "channels", "description": "Channel registration and management"},
        {"name": "integration-proxy", "description": "Credential-injecting API proxy — forwards requests to 300+ provider APIs with automatic OAuth2/API-key injection, token refresh, rate limiting, and optional unified data normalization"},
        {"name": "providers", "description": "Integration provider catalog"},
        {"name": "query", "description": "Query endpoint for data lookups"},
        {"name": "chat", "description": "Chat UI and conversational interface"},
    ],
)

from .middleware import ApiKeyAuthMiddleware, IpAllowlistMiddleware, RateLimitMiddleware

app.add_middleware(RateLimitMiddleware)
app.add_middleware(IpAllowlistMiddleware)
app.add_middleware(ApiKeyAuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.WGW_CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    if config.OTEL_ENABLED:
        FastAPIInstrumentor.instrument_app(app)
except Exception:
    pass

app.include_router(health.router)
app.include_router(chat_ui.router)
app.include_router(webhooks.router)
app.include_router(channels.router)
app.include_router(query.router)
app.include_router(providers.router)
app.include_router(api_proxy.router)
app.include_router(integration_proxy.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "webhook-gateway",
        "version": "0.1.0",
        "docs": "/docs",
        "chat": "/chat",
        "proxy": "/proxy/{provider_key}/{path}",
        "providers": "/providers",
        "openclaw_ui": "/oc/",
    }
