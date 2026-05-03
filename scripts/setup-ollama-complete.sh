#!/bin/bash
# ==============================================================================
# Complete VM Setup: Ollama + GPU + optional model
# ==============================================================================
# Run this on the VM to install everything and optionally pull/run a specific model.
# Usage: ./setup-ollama-complete.sh [OLLAMA_MODEL]
#   or:  OLLAMA_MODEL=gemma3:12b ./setup-ollama-complete.sh
# Default model: gemma3:27b
# ==============================================================================

set -e

# Model to pull and run: from first argument, or OLLAMA_MODEL env, or default
OLLAMA_MODEL="${1:-${OLLAMA_MODEL:-gemma3:27b}}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() { echo ""; echo -e "${BLUE}======== $1 ========${NC}"; echo ""; }
print_ok() { echo -e "${GREEN}✅ $1${NC}"; }
print_warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_err() { echo -e "${RED}❌ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

# ------------------------------------------------------------------------------
# 0. Install Docker if missing
# ------------------------------------------------------------------------------
print_header "0. Docker"

if command -v docker &> /dev/null && docker info &> /dev/null 2>&1; then
    print_ok "Docker already installed and usable"
    DOCKER="docker"
elif command -v docker &> /dev/null && sudo docker info &> /dev/null 2>&1; then
    print_ok "Docker installed (using sudo for this session)"
    DOCKER="sudo docker"
else
    print_info "Installing Docker..."
    sudo apt-get update -y
    sudo apt-get install -y curl ca-certificates gnupg
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "${VERSION_CODENAME:-bookworm}") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker "$USER" 2>/dev/null || true
    if docker info &> /dev/null 2>&1; then
        DOCKER="docker"
    else
        DOCKER="sudo docker"
    fi
    print_ok "Docker installed"
fi

# ------------------------------------------------------------------------------
# 1. Stop any existing containers
# ------------------------------------------------------------------------------
print_header "1. Cleanup"
$DOCKER stop ollama-wrapper ollama 2>/dev/null || true
$DOCKER rm ollama-wrapper ollama 2>/dev/null || true
print_ok "Cleaned up old containers"

# ------------------------------------------------------------------------------
# 2. Install NVIDIA drivers if GPU present
# ------------------------------------------------------------------------------
print_header "2. GPU Setup"

if lspci | grep -i nvidia > /dev/null; then
    print_info "NVIDIA GPU detected"
    
    if ! command -v nvidia-smi &> /dev/null; then
        print_info "Installing NVIDIA drivers (this takes 5-10 minutes)..."
        
        # Install prerequisites
        sudo apt-get update
        sudo apt-get install -y linux-headers-$(uname -r) build-essential dkms
        
        # Use NVIDIA's official runfile installer (most reliable)
        DRIVER_VERSION="535.183.01"
        DRIVER_URL="https://us.download.nvidia.com/tesla/${DRIVER_VERSION}/NVIDIA-Linux-x86_64-${DRIVER_VERSION}.run"
        
        print_info "Downloading NVIDIA driver ${DRIVER_VERSION}..."
        wget -q --show-progress "${DRIVER_URL}" -O /tmp/nvidia-installer.run
        
        print_info "Installing driver (silent mode)..."
        sudo sh /tmp/nvidia-installer.run --silent --dkms
        
        rm /tmp/nvidia-installer.run
        
        print_warn "GPU drivers installed. REBOOT REQUIRED to load them."
        print_warn "Run: sudo reboot"
        print_warn "Then SSH back in and run this script again."
        exit 0
    else
        print_ok "NVIDIA drivers already installed"
        nvidia-smi
    fi
    
    # Install NVIDIA Container Toolkit
    if ! dpkg -l | grep -q nvidia-container-toolkit; then
        print_info "Installing NVIDIA Container Toolkit..."
        curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
        curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
          sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
          sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
        sudo apt-get update
        sudo apt-get install -y nvidia-container-toolkit
        sudo nvidia-ctk runtime configure --runtime=docker
        sudo systemctl restart docker
        print_ok "NVIDIA Container Toolkit installed"
    else
        print_ok "NVIDIA Container Toolkit already installed"
    fi
    
    GPU_FLAG="--gpus all"
else
    print_info "No NVIDIA GPU detected (CPU mode)"
    GPU_FLAG=""
fi

# ------------------------------------------------------------------------------
# 3. Start Ollama container with GPU
# ------------------------------------------------------------------------------
print_header "3. Start Ollama"

print_info "Starting Ollama container..."
$DOCKER run -d --rm --name ollama $GPU_FLAG \
  -p 11434:11434 \
  -v /var/lib/ollama:/root/.ollama \
  ollama/ollama serve

print_info "Waiting for Ollama to start..."
sleep 10

if curl -s http://127.0.0.1:11434/api/tags > /dev/null; then
    print_ok "Ollama is running on port 11434"
else
    print_err "Ollama failed to start"
    $DOCKER logs ollama
    exit 1
fi

# ------------------------------------------------------------------------------
# 4. Pull model
# ------------------------------------------------------------------------------
print_header "4. Pull model: $OLLAMA_MODEL"

print_info "Pulling $OLLAMA_MODEL (this may take several minutes)..."
$DOCKER exec ollama ollama pull "$OLLAMA_MODEL"

print_ok "Model $OLLAMA_MODEL downloaded"

# ------------------------------------------------------------------------------
# 5. Start wrapper container
# ------------------------------------------------------------------------------
print_header "5. Start OpenAI-compatible wrapper"

# Ensure wrapper image exists
if [[ -f ~/ollama-openai-wrapper/wrapper.py ]]; then
    cd ~/ollama-openai-wrapper
    $DOCKER build -t mem-dog-ollama-wrapper:latest . 2>/dev/null || {
        print_warn "Wrapper image not built yet; skipping wrapper"
    }
    
    $DOCKER run -d --rm --name ollama-wrapper \
      --network host \
      -e OLLAMA_BASE_URL=http://127.0.0.1:11434 \
      mem-dog-ollama-wrapper:latest 2>/dev/null || {
        print_warn "Wrapper not available; using Ollama directly"
    }
fi

sleep 3

# ------------------------------------------------------------------------------
# 6. Test
# ------------------------------------------------------------------------------
print_header "6. Test $OLLAMA_MODEL"

print_info "Testing with Ollama API directly..."
RESPONSE=$($DOCKER exec ollama ollama run "$OLLAMA_MODEL" "Say hello in 5 words" --verbose=false 2>/dev/null || echo "error")

if [[ "$RESPONSE" != "error" ]]; then
    print_ok "$OLLAMA_MODEL is working!"
    echo "Response: $RESPONSE"
else
    print_warn "Direct test had issues; Ollama may still be loading the model"
fi

# Test wrapper if running
if $DOCKER ps | grep -q ollama-wrapper; then
    print_info "Testing wrapper API..."
    curl -s -X POST http://localhost:8000/v1/chat/completions \
      -H 'Content-Type: application/json' \
      -d "{\"model\":\"$OLLAMA_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Hi\"}],\"max_tokens\":10}" | head -c 200
    echo ""
fi

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------
print_header "Setup Complete"

echo "Ollama:     running on port 11434 (GPU: ${GPU_FLAG:-CPU})"
echo "Model:      $OLLAMA_MODEL (loaded)"
echo "Wrapper:    http://0.0.0.0:8000 (if available)"
echo ""
echo "Test commands:"
echo "  $DOCKER exec ollama ollama run $OLLAMA_MODEL 'Hello'"
echo "  curl http://127.0.0.1:11434/api/tags"
echo "  curl http://localhost:8000/health"
echo "  curl -X POST http://localhost:8000/v1/chat/completions \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"model\":\"$OLLAMA_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Hello\"}]}'"
echo ""

if [[ -z "$GPU_FLAG" ]]; then
    print_warn "Running on CPU (no GPU). Models will be slower."
    print_info "To use GPU: install drivers, reboot, and run this script again."
fi

print_ok "Done"
