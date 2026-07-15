FROM python:3.12-slim

WORKDIR /app

# Install agent dependencies before copying source so Docker caches this layer.
COPY webhook_agent/requirements.txt requirements.txt
COPY webhook_agent/requirements-docling.txt requirements-docling.txt
RUN pip install --no-cache-dir -r requirements.txt
# Opt-in Docling (larger wheel). Default GKE/processor images skip it; pypdf remains.
ARG INSTALL_DOCLING=false
RUN if [ "$INSTALL_DOCLING" = "true" ]; then \
      pip install --no-cache-dir -r requirements-docling.txt; \
    fi

# Copy agent source — the 'webhook_agent' directory is the ADK agent package.
COPY webhook_agent/ webhook_agent/

# Copy the direct FastAPI server and entrypoint.
COPY server.py server.py
COPY entrypoint.sh entrypoint.sh
RUN chmod +x entrypoint.sh

# Cloud Run injects PORT; entrypoint.sh falls back to 8080 if not set.
CMD ["./entrypoint.sh"]
