"""Configuration from environment variables."""

import os

MEM_DOG_API_URL = os.getenv("MEM_DOG_API_URL", "http://localhost:8080")
PORT = int(os.getenv("PORT", "8090"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
