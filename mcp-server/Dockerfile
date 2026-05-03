FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1

# Install the client SDK (copied from repo root by docker build context)
COPY client/ /tmp/client/
RUN pip install --no-cache-dir /tmp/client/ && rm -rf /tmp/client/

# Install MCP server dependencies
COPY mcp-server/pyproject.toml ./pyproject.toml
RUN pip install --no-cache-dir "mcp[cli]>=1.9.0" "fastapi>=0.115.0" "uvicorn[standard]>=0.27.0" "httpx>=0.28.1,<1.0.0" "pydantic>=2.11.0"

# Copy server code
COPY mcp-server/app/ ./app/

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
