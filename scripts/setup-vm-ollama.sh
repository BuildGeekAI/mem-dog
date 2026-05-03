#!/bin/bash
# ==============================================================================
# VM Setup Script for Ollama Model Server
# ==============================================================================
# This script installs and configures Ollama on a GCP VM instance
# Run this script on the VM after creation
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/your-org/mem-dog/main/scripts/setup-vm-ollama.sh | bash
#   OR
#   wget -O - https://raw.githubusercontent.com/your-org/mem-dog/main/scripts/setup-vm-ollama.sh | bash
#   OR
#   Copy this script to the VM and run: chmod +x setup-vm-ollama.sh && ./setup-vm-ollama.sh
# ==============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# ==============================================================================
# Step 1: Update System
# ==============================================================================

print_header "Step 1: Updating System"

print_info "Updating package lists..."
sudo apt-get update -y

print_info "Installing essential packages..."
sudo apt-get install -y \
    curl \
    wget \
    git \
    build-essential \
    software-properties-common

print_success "System updated"

# ==============================================================================
# Step 2: Install NVIDIA Drivers (if GPU present)
# ==============================================================================

print_header "Step 2: Checking for GPU"

if lspci | grep -i nvidia > /dev/null; then
    print_info "NVIDIA GPU detected, installing drivers..."
    
    # Install kernel headers
    sudo apt-get install -y linux-headers-$(uname -r)
    
    # Install NVIDIA drivers
    print_info "Installing NVIDIA drivers (this may take 5-10 minutes)..."
    sudo apt-get install -y nvidia-driver nvidia-cuda-toolkit
    
    print_success "NVIDIA drivers installed"
    print_warning "A reboot is required to load GPU drivers"
    print_info "After reboot, verify with: nvidia-smi"
else
    print_info "No NVIDIA GPU detected, skipping driver installation"
fi

# ==============================================================================
# Step 3: Install Ollama
# ==============================================================================

print_header "Step 3: Installing Ollama"

if command -v ollama &> /dev/null; then
    print_info "Ollama is already installed"
    ollama --version
else
    print_info "Downloading and installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    print_success "Ollama installed"
fi

# ==============================================================================
# Step 4: Configure Ollama Service
# ==============================================================================

print_header "Step 4: Configuring Ollama Service"

print_info "Creating systemd service for Ollama..."

sudo tee /etc/systemd/system/ollama.service > /dev/null <<EOF
[Unit]
Description=Ollama Service
After=network-online.target

[Service]
ExecStart=/usr/local/bin/ollama serve
User=$USER
Group=$USER
Restart=always
RestartSec=3
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_ORIGINS=*"

[Install]
WantedBy=default.target
EOF

print_info "Reloading systemd daemon..."
sudo systemctl daemon-reload

print_info "Enabling Ollama service..."
sudo systemctl enable ollama

print_info "Starting Ollama service..."
sudo systemctl start ollama

sleep 5

if sudo systemctl is-active --quiet ollama; then
    print_success "Ollama service is running"
else
    print_error "Ollama service failed to start"
    sudo systemctl status ollama
    exit 1
fi

# ==============================================================================
# Step 5: Create OpenAI-Compatible API Wrapper
# ==============================================================================

print_header "Step 5: Creating OpenAI-Compatible API Wrapper"

print_info "Installing Python and dependencies..."
sudo apt-get install -y python3 python3-pip python3-venv

print_info "Creating API wrapper directory..."
mkdir -p ~/ollama-openai-wrapper
cd ~/ollama-openai-wrapper

print_info "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

print_info "Installing FastAPI and dependencies..."
pip install fastapi uvicorn httpx pydantic

print_info "Creating OpenAI-compatible API wrapper..."
cat > wrapper.py <<'WRAPPER_EOF'
#!/usr/bin/env python3
"""
OpenAI-compatible API wrapper for Ollama
Maps OpenAI /v1/chat/completions format to Ollama API
"""
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import time

app = FastAPI(title="Ollama OpenAI Wrapper")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_BASE_URL = "http://localhost:11434"

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 512
    stream: Optional[bool] = False

class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]

@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                return {"status": "ok", "ollama": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ollama not available: {str(e)}")

@app.get("/v1/models")
async def list_models():
    """List available models"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                ollama_models = response.json().get("models", [])
                models = [{"id": m["name"], "object": "model", "owned_by": "ollama"} 
                         for m in ollama_models]
                return {"object": "list", "data": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    """OpenAI-compatible chat completions endpoint"""
    try:
        # Convert OpenAI format to Ollama format
        ollama_messages = [{"role": msg.role, "content": msg.content} 
                          for msg in request.messages]
        
        ollama_request = {
            "model": request.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            }
        }
        
        # Call Ollama API
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json=ollama_request
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, 
                                   detail=f"Ollama error: {response.text}")
            
            ollama_response = response.json()
            
            # Convert Ollama response to OpenAI format
            return ChatResponse(
                id=f"chatcmpl-{int(time.time())}",
                created=int(time.time()),
                model=request.model,
                choices=[{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": ollama_response.get("message", {}).get("content", "")
                    },
                    "finish_reason": "stop"
                }],
                usage={
                    "prompt_tokens": ollama_response.get("prompt_eval_count", 0),
                    "completion_tokens": ollama_response.get("eval_count", 0),
                    "total_tokens": (ollama_response.get("prompt_eval_count", 0) + 
                                    ollama_response.get("eval_count", 0))
                }
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
WRAPPER_EOF

chmod +x wrapper.py

print_success "API wrapper created"

# Create systemd service for wrapper
print_info "Creating systemd service for API wrapper..."

sudo tee /etc/systemd/system/ollama-wrapper.service > /dev/null <<EOF
[Unit]
Description=Ollama OpenAI-Compatible API Wrapper
After=network-online.target ollama.service
Requires=ollama.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/ollama-openai-wrapper
ExecStart=$HOME/ollama-openai-wrapper/venv/bin/python wrapper.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

print_info "Reloading systemd daemon..."
sudo systemctl daemon-reload

print_info "Enabling wrapper service..."
sudo systemctl enable ollama-wrapper

print_info "Starting wrapper service..."
sudo systemctl start ollama-wrapper

sleep 3

if sudo systemctl is-active --quiet ollama-wrapper; then
    print_success "Ollama wrapper service is running on port 8000"
else
    print_error "Ollama wrapper service failed to start"
    sudo systemctl status ollama-wrapper
    exit 1
fi

# ==============================================================================
# Step 6: Summary
# ==============================================================================

print_header "Installation Complete!"

echo ""
echo "Services Status:"
echo "  Ollama:     $(sudo systemctl is-active ollama)"
echo "  Wrapper:    $(sudo systemctl is-active ollama-wrapper)"
echo ""
echo "Available Commands:"
echo "  ollama list                          - List downloaded models"
echo "  ollama pull gemma3:27b              - Download Gemma 3 27B"
echo "  ollama run gemma3:27b               - Run model interactively"
echo "  sudo systemctl status ollama         - Check Ollama service"
echo "  sudo systemctl status ollama-wrapper - Check wrapper service"
echo ""
echo "API Endpoints:"
echo "  Health:  http://0.0.0.0:8000/health"
echo "  Models:  http://0.0.0.0:8000/v1/models"
echo "  Chat:    http://0.0.0.0:8000/v1/chat/completions"
echo ""
echo "Next Steps:"
echo "  1. Download a model: ollama pull gemma3:27b"
echo "  2. Test health: curl http://localhost:8000/health"
echo "  3. Register VM in mem-dog (from your local machine)"
echo ""

if lspci | grep -i nvidia > /dev/null && ! command -v nvidia-smi &> /dev/null; then
    print_warning "GPU drivers installed but not loaded"
    print_warning "Run 'sudo reboot' to load GPU drivers"
    echo ""
fi

print_success "Setup complete! 🚀"
