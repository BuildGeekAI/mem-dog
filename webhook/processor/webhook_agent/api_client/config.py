"""Shared configuration for the memdog API client.

All API client modules read from this single source of truth so that
the base URL, timeouts, and feature flags are never duplicated.
"""

import os

# Base URL of the memdog API (set via env var in production)
MEM_DOG_API_URL: str = os.environ.get("MEM_DOG_API_URL", "http://localhost:8080")

# API key for authenticating with the memdog API (required when API has API_KEY set)
MEM_DOG_API_KEY: str = os.environ.get("MEM_DOG_API_KEY", "")

# Default user for agent-owned memories
AGENT_USER_ID: str = os.environ.get("AGENT_USER_ID", "00000000-0000-0000-0000-000000000001")

# Request timeouts (seconds)
DEFAULT_TIMEOUT: int = 15
UPLOAD_TIMEOUT: int = 30

# ---------------------------------------------------------------------------
# Staging bucket — downloaded content is written here before analysis
# ---------------------------------------------------------------------------

# GCS bucket name for staged downloads.  When empty, GCS writes are skipped
# and content is only held in memory (safe for local dev).
WEBHOOK_STAGING_BUCKET: str = os.environ.get("WEBHOOK_STAGING_BUCKET", "")

# ---------------------------------------------------------------------------
# AI enrichment — viewpoints + embeddings posted to the memdog AI API
# ---------------------------------------------------------------------------

# AI engine identifier forwarded to POST /api/v1/ai/viewpoints and
# POST /api/v1/ai/embeddings.  "model_server" tells the API to use the
# Ollama model server (Cloud Run B).
AI_ENGINE_TYPE: str = os.environ.get("AI_ENGINE_TYPE", "model_server")

# Model string used for embedding generation via the Gemini API.
AI_EMBEDDING_MODEL: str = os.environ.get("AI_EMBEDDING_MODEL", "embeddinggemma")

# Default prompt ID for viewpoint generation.  Created via
# POST /api/v1/ai/prompts with the "webhook-analysis" template.
VIEWPOINT_PROMPT_ID: str = os.environ.get("VIEWPOINT_PROMPT_ID", "")
