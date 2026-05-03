"""Chat UI router — serves the embedded webchat interface at ``/chat``."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["chat-ui"])

_CHAT_HTML = Path(__file__).resolve().parent.parent / "static" / "chat.html"


@router.get("/chat", include_in_schema=False)
async def chat_ui() -> FileResponse:
    return FileResponse(_CHAT_HTML, media_type="text/html")
