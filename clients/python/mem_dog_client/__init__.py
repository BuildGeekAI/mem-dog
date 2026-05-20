"""Mem-Dog Python client for the Mem-Dog private AI system API.

Talks to the API layer via REST. Supports data, memories, users, tags,
AI features (prompts, embeddings, viewpoints, query), and more.
"""

from mem_dog_client.client import MemDogClient
from mem_dog_client.simple import MemDog

__all__ = ["MemDogClient", "MemDog"]
