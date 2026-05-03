#!/bin/bash
# ==============================================================================
# VM Setup Script: Ollama via Docker
# ==============================================================================
# Installs Docker (and NVIDIA Container Toolkit if GPU), runs Ollama in a
# container, and sets up the OpenAI-compatible wrapper. Run on the VM after
# creation.
#
# Usage:
#   From local: gcloud compute scp scripts/setup-vm-ollama-docker.sh VM_NAME:~ ...
#   On VM: chmod +x setup-vm-ollama-docker.sh && ./setup-vm-ollama-docker.sh
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() { echo ""; echo -e "${BLUE}========================================${NC}"; echo -e "${BLUE}  $1${NC}"; echo -e "${BLUE}========================================${NC}"; echo ""; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

# ------------------------------------------------------------------------------
# Step 1: System update + Docker
# ------------------------------------------------------------------------------
print_header "Step 1: System update and Docker"

sudo apt-get update -y
sudo apt-get install -y curl ca-certificates gnupg

if command -v docker &> /dev/null; then
    print_info "Docker already installed"
    docker --version
else
    print_info "Installing Docker..."
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "${VERSION_CODENAME:-bookworm}") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker "$USER"
    print_success "Docker installed (log out/in or run 'newgrp docker' for group)"
fi

# Allow current session to use docker if possible
if ! docker info &> /dev/null; then
    print_warning "Running Docker commands with sudo for this session"
    DOCKER="sudo docker"
else
    DOCKER="docker"
fi

# ------------------------------------------------------------------------------
# Step 2: NVIDIA Container Toolkit (if GPU)
# ------------------------------------------------------------------------------
print_header "Step 2: GPU support (NVIDIA Container Toolkit)"

if lspci | grep -i nvidia > /dev/null; then
    if dpkg -l | grep -q nvidia-container-toolkit; then
        print_info "NVIDIA Container Toolkit already installed"
    else
        print_info "Installing NVIDIA Container Toolkit..."
        curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
        curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
        sudo apt-get update -y
        sudo apt-get install -y nvidia-container-toolkit
        sudo nvidia-ctk runtime configure --runtime=docker
        print_success "NVIDIA Container Toolkit installed"
    fi
else
    print_info "No NVIDIA GPU detected; Ollama will run on CPU in Docker"
fi

# ------------------------------------------------------------------------------
# Step 3: Ollama container (systemd)
# ------------------------------------------------------------------------------
print_header "Step 3: Ollama via Docker"

OLLAMA_DATA="${OLLAMA_DATA:-/var/lib/ollama}"
sudo mkdir -p "$OLLAMA_DATA"
# Leave owned by root so the container (running as root) can write
sudo chmod 755 "$OLLAMA_DATA"

# Optional: use GPU in container (systemd runs as root, so plain "docker")
NVIDIA_RUNTIME=""
if lspci | grep -i nvidia > /dev/null && command -v nvidia-smi &> /dev/null; then
    NVIDIA_RUNTIME="--gpus all"
fi

# Shared network so wrapper container can reach ollama by hostname
$DOCKER network create ollama-net 2>/dev/null || true

# Use foreground run so systemd tracks the container; if it exits, systemd restarts it
sudo tee /etc/systemd/system/ollama-docker.service > /dev/null <<SVCEOF
[Unit]
Description=Ollama (Docker)
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=simple
ExecStartPre=-/usr/bin/docker stop ollama 2>/dev/null
ExecStartPre=-/usr/bin/docker rm ollama 2>/dev/null
ExecStartPre=/usr/bin/docker network create ollama-net 2>/dev/null || true
ExecStart=/usr/bin/docker run --rm --name ollama --network ollama-net NVIDIA_RUNTIME_PLACEHOLDER -v OLLAMA_DATA_PLACEHOLDER:/root/.ollama -p 11434:11434 ollama/ollama serve
ExecStop=/usr/bin/docker stop ollama
TimeoutStartSec=300
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

sudo sed -i "s|OLLAMA_DATA_PLACEHOLDER|$OLLAMA_DATA|g" /etc/systemd/system/ollama-docker.service
sudo sed -i "s|NVIDIA_RUNTIME_PLACEHOLDER|$NVIDIA_RUNTIME|g" /etc/systemd/system/ollama-docker.service

sudo systemctl daemon-reload
sudo systemctl enable ollama-docker
sudo systemctl start ollama-docker

print_info "Waiting for Ollama container to be ready..."
sleep 10
if $DOCKER ps | grep -q ollama; then
    print_success "Ollama container is running"
else
    print_error "Ollama container failed to start"
    $DOCKER ps -a | grep ollama || true
    exit 1
fi

# ------------------------------------------------------------------------------
# Step 4: OpenAI-compatible wrapper (Docker, same network as Ollama)
# ------------------------------------------------------------------------------
print_header "Step 4: OpenAI-compatible API wrapper (Docker)"

WRAPPER_DIR="$HOME/ollama-openai-wrapper"
mkdir -p "$WRAPPER_DIR"
cd "$WRAPPER_DIR"

# Dockerfile for wrapper (reads OLLAMA_BASE_URL from env)
cat > Dockerfile <<'DFEOF'
FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn httpx pydantic
COPY wrapper.py .
ENV OLLAMA_BASE_URL=http://ollama:11434
EXPOSE 8000
CMD ["uvicorn", "wrapper:app", "--host", "0.0.0.0", "--port", "8000"]
DFEOF

# wrapper.py: clear 503 when Ollama unreachable; /health returns JSON (no exception)
cat > wrapper.py <<'WRAPPER_EOF'
import os
import time
from typing import Any, Dict, List, Optional
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_UNREACHABLE = f"Ollama not reachable at {OLLAMA_BASE_URL}. Start: docker run -d --rm --name ollama -p 11434:11434 -v /var/lib/ollama:/root/.ollama ollama/ollama serve"

def _conn_err(e):
    s = str(e).lower()
    return isinstance(e, httpx.ConnectError) or "connection" in s or "attempts failed" in s or "name or service not known" in s

app = FastAPI(title="Ollama OpenAI Wrapper")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class Message(BaseModel): role: str; content: str
class ChatRequest(BaseModel): model: str; messages: List[Message]; temperature: Optional[float] = 0.7; max_tokens: Optional[int] = 512; stream: Optional[bool] = False
class ChatResponse(BaseModel): id: str; object: str = "chat.completion"; created: int; model: str; choices: List[Dict[str, Any]]; usage: Dict[str, int]

@app.get("/health")
async def health():
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{OLLAMA_BASE_URL}/api/tags")
            return {"status": "ok", "ollama": "connected"} if r.status_code == 200 else {"status": "error", "detail": r.text}
    except httpx.ConnectError:
        return {"status": "degraded", "ollama": "unreachable", "detail": OLLAMA_UNREACHABLE}
    except Exception as e:
        if _conn_err(e): return {"status": "degraded", "ollama": "unreachable", "detail": OLLAMA_UNREACHABLE}
        raise

@app.get("/v1/models")
async def list_models():
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(f"{OLLAMA_BASE_URL}/api/tags")
            if r.status_code != 200: raise HTTPException(502, r.text)
            return {"object": "list", "data": [{"id": m["name"], "object": "model", "owned_by": "ollama"} for m in r.json().get("models", [])]}
    except httpx.ConnectError:
        raise HTTPException(503, detail=OLLAMA_UNREACHABLE)
    except Exception as e:
        if _conn_err(e): raise HTTPException(503, detail=OLLAMA_UNREACHABLE) from None
        raise

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    try:
        async with httpx.AsyncClient(timeout=300.0) as c:
            r = await c.post(f"{OLLAMA_BASE_URL}/api/chat", json={"model": request.model, "messages": [{"role": m.role, "content": m.content} for m in request.messages], "stream": False, "options": {"temperature": request.temperature, "num_predict": request.max_tokens}})
            if r.status_code != 200: raise HTTPException(r.status_code, r.text)
            d = r.json(); msg = d.get("message", {}).get("content", "")
            return ChatResponse(id=f"chatcmpl-{int(time.time())}", created=int(time.time()), model=request.model, choices=[{"index": 0, "message": {"role": "assistant", "content": msg}, "finish_reason": "stop"}], usage={"prompt_tokens": d.get("prompt_eval_count", 0), "completion_tokens": d.get("eval_count", 0), "total_tokens": d.get("prompt_eval_count", 0) + d.get("eval_count", 0)})
    except httpx.ConnectError:
        raise HTTPException(503, detail=OLLAMA_UNREACHABLE)
    except Exception as e:
        if _conn_err(e): raise HTTPException(503, detail=OLLAMA_UNREACHABLE) from None
        raise
WRAPPER_EOF

print_info "Building wrapper image..."
$DOCKER build -t mem-dog-ollama-wrapper:latest . 2>/dev/null || sudo docker build -t mem-dog-ollama-wrapper:latest .

# Systemd unit for wrapper: use host network so it always reaches Ollama on host port 11434
# (avoids "name not known" if ollama was ever started without --network ollama-net)
sudo tee /etc/systemd/system/ollama-wrapper-docker.service > /dev/null <<EOF
[Unit]
Description=Ollama OpenAI Wrapper (Docker)
After=ollama-docker.service network-online.target
Requires=ollama-docker.service

[Service]
Type=simple
ExecStartPre=-/usr/bin/docker stop ollama-wrapper 2>/dev/null
ExecStartPre=-/usr/bin/docker rm ollama-wrapper 2>/dev/null
ExecStartPre=/bin/sleep 3
ExecStart=/usr/bin/docker run --rm --name ollama-wrapper --network host -e OLLAMA_BASE_URL=http://127.0.0.1:11434 mem-dog-ollama-wrapper:latest
ExecStop=/usr/bin/docker stop ollama-wrapper
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ollama-wrapper-docker
sudo systemctl start ollama-wrapper-docker
sleep 5
if sudo systemctl is-active --quiet ollama-wrapper-docker 2>/dev/null || $DOCKER ps 2>/dev/null | grep -q ollama-wrapper; then
    print_success "Wrapper container running on port 8000"
else
    print_warning "Wrapper may still be starting; check: sudo systemctl status ollama-wrapper-docker"
fi

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------
print_header "Done"

echo "Ollama:     Docker (ollama/ollama), port 11434, network ollama-net"
echo "Wrapper:    Docker (mem-dog-ollama-wrapper), port 8000, network ollama-net"
echo ""
echo "Pull a model:  docker exec ollama ollama pull gemma3:27b"
echo "List models:   docker exec ollama ollama list"
echo "Restart both:  sudo systemctl restart ollama-docker ollama-wrapper-docker"
echo ""
print_success "Setup complete (all Docker)"