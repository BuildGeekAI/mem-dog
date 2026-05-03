"""Cryptographic utilities for API key encryption/decryption.

Uses Fernet (symmetric AES-256) with a master key from environment variable.
The master key must be a 32-byte base64-encoded string generated via:

    from cryptography.fernet import Fernet
    print(Fernet.generate_key().decode())

Set the result as MASTER_ENCRYPTION_KEY in your environment.
"""

import base64
import logging
import os

logger = logging.getLogger("mem_dog.crypto")

# Master encryption key from environment
MASTER_KEY = os.getenv("MASTER_ENCRYPTION_KEY", "")

if not MASTER_KEY:
    logger.warning(
        "MASTER_ENCRYPTION_KEY not set; API key encryption will fail. "
        "Generate a key: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
    )

try:
    from cryptography.fernet import Fernet
    _cipher = Fernet(MASTER_KEY.encode()) if MASTER_KEY else None
except ImportError:
    logger.error("cryptography package not installed; cannot encrypt API keys")
    _cipher = None
except Exception as e:
    logger.error(f"Failed to initialize Fernet cipher: {e}")
    _cipher = None


def encrypt_api_key(plain_key: str) -> str:
    """Encrypt an API key for storage in Postgres.
    
    Args:
        plain_key: Plain text API key (e.g., "sk-...")
    
    Returns:
        Base64-encoded encrypted bytes as a string
    
    Raises:
        RuntimeError: If encryption key is not configured or crypto failed
    """
    if not _cipher:
        raise RuntimeError(
            "Cannot encrypt API key: MASTER_ENCRYPTION_KEY not configured or cryptography not available"
        )
    
    encrypted_bytes = _cipher.encrypt(plain_key.encode())
    return base64.b64encode(encrypted_bytes).decode()


def decrypt_api_key(encrypted: str) -> str:
    """Decrypt an API key from storage.
    
    Args:
        encrypted: Base64-encoded encrypted string from Postgres
    
    Returns:
        Plain text API key
    
    Raises:
        RuntimeError: If encryption key is not configured or decryption failed
    """
    if not _cipher:
        raise RuntimeError(
            "Cannot decrypt API key: MASTER_ENCRYPTION_KEY not configured or cryptography not available"
        )
    
    encrypted_bytes = base64.b64decode(encrypted.encode())
    decrypted = _cipher.decrypt(encrypted_bytes)
    return decrypted.decode()


def is_encryption_available() -> bool:
    """Check if encryption is properly configured."""
    return _cipher is not None
