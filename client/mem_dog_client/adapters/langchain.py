"""LangChain adapter for memdog memory.

Provides:
- ``MemDogChatMessageHistory`` — drop-in ``BaseChatMessageHistory`` for conversation memory.
- ``MemDogRetriever`` — ``BaseRetriever`` that searches memdog via semantic/AI query.

Usage::

    from mem_dog_client.adapters.langchain import MemDogChatMessageHistory, MemDogRetriever
    from mem_dog_client import MemDog

    m = MemDog("http://localhost:8080", user_id="user1")
    history = MemDogChatMessageHistory(m, memory_id="mem_conversation_abc")
    retriever = MemDogRetriever(m, search_kwargs={"limit": 5})

Requires: ``pip install langchain-core``
"""

from __future__ import annotations

from typing import Any, List, Optional, Sequence

try:
    from langchain_core.chat_history import BaseChatMessageHistory
    from langchain_core.documents import Document
    from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
    from langchain_core.retrievers import BaseRetriever
    from langchain_core.callbacks import CallbackManagerForRetrieverRun
except ImportError as e:
    raise ImportError(
        "LangChain adapter requires langchain-core. "
        "Install with: pip install memdog-client[langchain]"
    ) from e

from mem_dog_client.simple import MemDog


class MemDogChatMessageHistory(BaseChatMessageHistory):
    """Chat message history backed by memdog.

    Each message is stored as a data item tagged with ``chat:true`` and
    ``role:<role>``, linked to a memdog memory (conversation).
    """

    def __init__(
        self,
        mem_dog: MemDog,
        memory_id: Optional[str] = None,
        memory_type: str = "conversation",
        user_id: Optional[str] = None,
    ) -> None:
        self._md = mem_dog
        self._memory_id = memory_id
        self._memory_type = memory_type
        self._user_id = user_id

    @property
    def messages(self) -> List[BaseMessage]:
        """Retrieve all messages from the memory."""
        results = self._md.search(
            "",
            memory_type=self._memory_type,
            memory_ids=[self._memory_id] if self._memory_id else None,
            limit=100,
            user_id=self._user_id,
        )
        messages: List[BaseMessage] = []
        for item in results:
            content = item.get("content", "")
            tags = item.get("tags", [])
            role = "human"
            for t in tags:
                if t.startswith("role:"):
                    role = t[5:]
                    break
            if role == "ai" or role == "assistant":
                messages.append(AIMessage(content=content))
            elif role == "system":
                messages.append(SystemMessage(content=content))
            else:
                messages.append(HumanMessage(content=content))
        return messages

    def add_message(self, message: BaseMessage) -> None:
        """Store a message in memdog."""
        role = "human"
        if isinstance(message, AIMessage):
            role = "ai"
        elif isinstance(message, SystemMessage):
            role = "system"

        self._md.add(
            content=message.content if isinstance(message.content, str) else str(message.content),
            tags=["chat:true", f"role:{role}"],
            memory_type=self._memory_type,
            memory_id=self._memory_id,
            user_id=self._user_id,
        )

    def clear(self) -> None:
        """Not implemented — memdog doesn't support bulk delete via simple API."""
        pass


class MemDogRetriever(BaseRetriever):
    """LangChain retriever backed by memdog search.

    Uses AI-powered RAG query when ``use_ai=True``, otherwise metadata search.
    """

    mem_dog: Any  # MemDog instance
    search_kwargs: dict = {}

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: Optional[CallbackManagerForRetrieverRun] = None,
    ) -> List[Document]:
        kwargs = {**self.search_kwargs}
        use_ai = kwargs.pop("use_ai", False)
        limit = kwargs.pop("limit", 10)

        results = self.mem_dog.search(query, limit=limit, use_ai=use_ai, **kwargs)
        docs: List[Document] = []
        for item in results:
            content = item.get("content") or item.get("response") or item.get("summary", "")
            metadata = {
                k: v for k, v in item.items()
                if k not in ("content", "response") and not isinstance(v, (dict, list))
            }
            docs.append(Document(page_content=str(content), metadata=metadata))
        return docs
