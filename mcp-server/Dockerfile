FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1

# Install the client SDK (copied from repo root by docker build context)
COPY clients/python/ /tmp/client/
RUN pip install --no-cache-dir /tmp/client/ && rm -rf /tmp/client/

# Install MCP server dependencies from pyproject.toml — single source of truth.
# mem-dog-client is filtered out: it is installed above from the local repo
# checkout, and is not published to PyPI.
COPY mcp-server/pyproject.toml ./pyproject.toml
RUN python -c "import tomllib; deps = tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']; open('/tmp/requirements.txt', 'w').write(chr(10).join(d for d in deps if not d.startswith('mem-dog-client')))" \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

# Copy server code
COPY mcp-server/app/ ./app/

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
