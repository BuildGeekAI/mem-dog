FROM python:3.11-slim

# Install uv via pip — avoids a COPY --from=ghcr.io step that can fail when
# Docker Desktop has no external DNS (common in restricted network environments).
RUN pip install --no-cache-dir uv

WORKDIR /app

# Storage backend is auto-detected at runtime:
#   - If GCP_PROJECT_ID or SYSTEM_CONFIG_BUCKET is set → "gcs"
#   - Otherwise → "local" (data stored in MEM_DOG_DATA_DIR)
# Can be forced with STORAGE_BACKEND=local or STORAGE_BACKEND=gcs.
ENV MEM_DOG_DATA_DIR="/data"
ENV ENVIRONMENT="development"
# Compile bytecode for faster startup; no installer metadata needed in the image
ENV UV_COMPILE_BYTECODE=1
ENV UV_NO_INSTALLER_METADATA=1

# Copy project manifest + lockfile first for better layer caching
COPY pyproject.toml uv.lock ./
# Install dependencies only (not the project itself) so this layer is cached
# when only application code changes.
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY . .

# Install the project (creates .venv with all deps + app on PYTHONPATH)
RUN uv sync --frozen --no-dev

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]
