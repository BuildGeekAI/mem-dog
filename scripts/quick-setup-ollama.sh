#!/bin/bash
# One script to install Docker + Ollama + Gemma 3 27B (CPU mode, works immediately)
set -e

echo "🚀 Installing Docker + Ollama + Gemma 3 27B..."

# Fix broken backports repo if present
sudo rm -f /etc/apt/sources.list.d/backports.list 2>/dev/null || true

# 1. Install Docker
if ! command -v docker &> /dev/null; then
  echo "📦 Installing Docker..."
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker $USER
  newgrp docker
fi

# 2. Start Ollama
echo "🦙 Starting Ollama..."
docker stop ollama 2>/dev/null || true
docker run -d --rm --name ollama -p 11434:11434 -v /var/lib/ollama:/root/.ollama ollama/ollama serve
sleep 10

# 3. Pull Gemma 3 27B
echo "📥 Pulling Gemma 2 27B (this takes 10-15 minutes)..."
docker exec ollama ollama pull gemma3:27b

# 4. Create wrapper
echo "🔧 Setting up OpenAI-compatible wrapper..."
mkdir -p ~/ollama-wrapper && cd ~/ollama-wrapper

cat > wrapper.py << 'EOF'
import os, time, httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class Message(BaseModel): role: str; content: str
class ChatRequest(BaseModel): model: str; messages: List[Message]; temperature: Optional[float] = 0.7; max_tokens: Optional[int] = 512
class ChatResponse(BaseModel): id: str; object: str = "chat.completion"; created: int; model: str; choices: List[Dict[str, Any]]; usage: Dict[str, int]

@app.get("/health")
async def health():
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{OLLAMA_BASE_URL}/api/tags")
            return {"status": "ok"} if r.status_code == 200 else {"status": "error"}
    except: return {"status": "degraded"}

@app.get("/v1/models")
async def list_models():
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.get(f"{OLLAMA_BASE_URL}/api/tags")
        if r.status_code != 200: raise HTTPException(502, r.text)
        return {"object": "list", "data": [{"id": m["name"], "object": "model"} for m in r.json().get("models", [])]}

@app.post("/v1/chat/completions")
async def chat(req: ChatRequest):
    async with httpx.AsyncClient(timeout=300.0) as c:
        r = await c.post(f"{OLLAMA_BASE_URL}/api/chat", json={"model": req.model, "messages": [{"role": m.role, "content": m.content} for m in req.messages], "stream": False, "options": {"temperature": req.temperature, "num_predict": req.max_tokens}})
        if r.status_code != 200: raise HTTPException(r.status_code, r.text)
        d = r.json()
        return ChatResponse(id=f"chatcmpl-{int(time.time())}", created=int(time.time()), model=req.model, choices=[{"index": 0, "message": {"role": "assistant", "content": d.get("message", {}).get("content", "")}, "finish_reason": "stop"}], usage={"prompt_tokens": d.get("prompt_eval_count", 0), "completion_tokens": d.get("eval_count", 0), "total_tokens": d.get("prompt_eval_count", 0) + d.get("eval_count", 0)})
EOF

cat > Dockerfile << 'EOF'
FROM python:3.11-slim
WORKDIR /app
RUN pip install fastapi uvicorn httpx pydantic
COPY wrapper.py .
EXPOSE 8000
CMD ["uvicorn", "wrapper:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

docker build -t ollama-wrapper .
docker stop ollama-wrapper 2>/dev/null || true
docker run -d --rm --name ollama-wrapper --network host ollama-wrapper

# 5. Test
echo ""
echo "✅ Setup complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Ollama:  http://localhost:11434"
echo "Wrapper: http://localhost:8000"
echo ""
echo "Test commands:"
echo "  docker exec ollama ollama run gemma3:27b 'Hello'"
echo "  curl http://localhost:8000/health"
echo "  curl http://localhost:8000/v1/models"
echo ""
echo "Chat:"
echo "  curl -X POST http://localhost:8000/v1/chat/completions \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"model\":\"gemma3:27b\",\"messages\":[{\"role\":\"user\",\"content\":\"Hi\"}]}'"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
