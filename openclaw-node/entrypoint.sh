#!/bin/sh
set -e

# Set environment variables for the coollabsio configure.js
export OPENCLAW_GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
export OPENCLAW_GATEWAY_BIND="${OPENCLAW_GATEWAY_BIND:-lan}"
export OPENCLAW_NO_RESPAWN=1
export NODE_COMPILE_CACHE=/var/tmp/openclaw-compile-cache
mkdir -p /var/tmp/openclaw-compile-cache

export OPENCLAW_STATE_DIR="${OPENCLAW_STATE_DIR:-/data/.openclaw}"
export OPENCLAW_WORKSPACE_DIR="${OPENCLAW_WORKSPACE_DIR:-/data/workspace}"
mkdir -p "$OPENCLAW_STATE_DIR" "$OPENCLAW_WORKSPACE_DIR"

echo "[memdog-entrypoint] Running configure..."
cd /opt/openclaw/app
node /app/scripts/configure.js 2>&1 || true

# Ensure wildcard origins so the memdog UI can connect via WebSocket
node -e "
const fs = require('fs');
const f = process.env.OPENCLAW_STATE_DIR + '/openclaw.json';
const c = JSON.parse(fs.readFileSync(f, 'utf8'));
if (c.gateway && c.gateway.controlUi) { c.gateway.controlUi.allowedOrigins = ['*']; }
fs.writeFileSync(f, JSON.stringify(c, null, 2));
" 2>/dev/null || true

echo "[memdog-entrypoint] Skipping doctor, starting nginx..."
# Generate minimal nginx config (reverse proxy 8080 -> 18789)
cat > /tmp/nginx.conf << 'NGINX'
worker_processes 1;
events { worker_connections 256; }
http {
    server {
        listen 8080;
        location / {
            proxy_pass http://127.0.0.1:18789;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_read_timeout 86400s;
        }
        location /healthz {
            proxy_pass http://127.0.0.1:18789/healthz;
            proxy_http_version 1.1;
        }
        location /readyz {
            proxy_pass http://127.0.0.1:18789/healthz;
            proxy_http_version 1.1;
        }
    }
}
NGINX
nginx -c /tmp/nginx.conf

echo "[memdog-entrypoint] Starting openclaw gateway run (port=$OPENCLAW_GATEWAY_PORT, bind=$OPENCLAW_GATEWAY_BIND)..."
exec openclaw gateway run --log-level debug
