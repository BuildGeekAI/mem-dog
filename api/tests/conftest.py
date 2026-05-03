"""
Test configuration and fixtures for API tests.
"""
import os
import pytest
from fastapi.testclient import TestClient

# Set test environment variables
os.environ["MASTER_ENCRYPTION_KEY"] = "dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcwo="  # Base64 encoded test key
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)

