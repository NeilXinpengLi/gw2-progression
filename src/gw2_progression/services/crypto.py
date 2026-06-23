"""Encryption utilities for credential storage."""

import base64
import hashlib
import os

from cryptography.fernet import Fernet

_SERVER_SECRET = os.environ.get("CREDENTIAL_SECRET", "gw2-progression-default-secret-change-in-production")


def _derive_fernet_key(secret: str) -> bytes:
    """Derive a 32-byte Fernet key from the server secret."""
    raw = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(raw)


_fernet = Fernet(_derive_fernet_key(_SERVER_SECRET))


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value (API key) for storage."""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a previously encrypted value."""
    return _fernet.decrypt(ciphertext.encode()).decode()


def fingerprint(key: str) -> str:
    """Return last 4 chars of a key for UI display."""
    return "..." + key[-4:] if len(key) > 4 else "****"
