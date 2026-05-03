#!/usr/bin/env python3
"""OpenAI-compatible API wrapper for Ollama. Use OLLAMA_BASE_URL env (e.g. http://ollama:11434 in Docker)."""
import os
import time
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

OLLAMA_UNREACHABLE_MSG = (
    f"Ollama is not reachable at {OLLAMA_BASE_URL}. "
    "Start the Ollama container: docker run -d --rm --name ollama -p 11434:11434 "
    "-v /var/lib/ollama:/root/.ollama ollama/ollama serve"
)

app = FastAPI(title="Ollama OpenAI Wrapper")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


def _is_connection_error(exc: Exception) -> bool:
    """True if the exception indicates Ollama is unreachable."""
    msg = str(exc).lower()
    return (
        isinstance(exc, httpx.ConnectError)
        or "connection" in msg
        or "attempts failed" in msg
        or "name or service not known" in msg
    )


@app.get("/health")
async def health():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            return {"status": "ok", "ollama": "connected"} if r.status_code == 200 else {"status": "error", "detail": r.text}
    except httpx.ConnectError:
        return {"status": "degraded", "ollama": "unreachable", "detail": OLLAMA_UNREACHABLE_MSG}
    except Exception as e:
        if _is_connection_error(e):
            return {"status": "degraded", "ollama": "unreachable", "detail": OLLAMA_UNREACHABLE_MSG}
        raise HTTPException(503, detail=str(e))


@app.get("/v1/models")
async def list_models():
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if r.status_code != 200:
                raise HTTPException(502, r.text)
            data = r.json()
            models = [
                {"id": m["name"], "object": "model", "owned_by": "ollama"}
                for m in data.get("models", [])
            ]
            return {"object": "list", "data": models}
    except httpx.ConnectError:
        raise HTTPException(503, detail=OLLAMA_UNREACHABLE_MSG)
    except Exception as e:
        if _is_connection_error(e):
            raise HTTPException(503, detail=OLLAMA_UNREACHABLE_MSG) from None
        raise


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    ollama_messages = [{"role": m.role, "content": m.content} for m in request.messages]
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            r = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": request.model,
                    "messages": ollama_messages,
                    "stream": False,
                    "options": {
                        "temperature": request.temperature,
                        "num_predict": request.max_tokens,
                    },
                },
            )
            if r.status_code != 200:
                raise HTTPException(r.status_code, r.text)
            data = r.json()
            msg = data.get("message", {}).get("content", "")
            return ChatResponse(
                id=f"chatcmpl-{int(time.time())}",
                created=int(time.time()),
                model=request.model,
                choices=[
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": msg},
                        "finish_reason": "stop",
                    }
                ],
                usage={
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0),
                    "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                },
            )
    except httpx.ConnectError:
        raise HTTPException(503, detail=OLLAMA_UNREACHABLE_MSG)
    except Exception as e:
        if _is_connection_error(e):
            raise HTTPException(503, detail=OLLAMA_UNREACHABLE_MSG) from None
        raise


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
