#!/bin/bash
# Entrypoint for the mem-dog webhook agent container (Cloud Run A).
#
# Runs a direct FastAPI server (server.py) that calls route_payload() without
# LLM orchestration.  Gemma 3 4B is not reliable enough at tool-calling to
# act as an orchestrator, so we bypass the ADK /run_sse path entirely.
#
# No model is downloaded here — LLM inference for classification and
# sub-agent enrichment is still delegated to the model server (Cloud Run B)
# at MODEL_SERVER_URL.

set -euo pipefail

PORT="${PORT:-8080}"

echo "[entrypoint] Starting mem-dog webhook agent server"
echo "[entrypoint] MODEL_SERVER_URL=${MODEL_SERVER_URL:-<not set>}"
echo "[entrypoint] MEM_DOG_API_URL=${MEM_DOG_API_URL:-<not set>}"

# For local development, load .env so all configured variables are available.
# On Cloud Run env vars are injected directly and this block is a no-op.
python3 - <<'PYEOF'
import os

def _load_dotenv(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

script_dir = os.path.dirname(os.path.abspath(__file__))
_load_dotenv(os.path.join(script_dir, "webhook_agent", ".env"))
PYEOF

echo "[entrypoint] Starting FastAPI server on port $PORT ..."

exec python3 -m uvicorn server:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --log-level info
