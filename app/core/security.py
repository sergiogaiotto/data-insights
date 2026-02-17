import hashlib
import secrets
from app.core.config import settings
from app.core.database import get_sync_connection


def hash_api_key(raw_key: str) -> str:
    """SHA256 + salt hash for API key storage."""
    salted = f"{settings.api_salt}{raw_key}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    """Generate a cryptographically secure API key."""
    return secrets.token_urlsafe(32)


def create_api_key(label: str) -> dict:
    """Create and store a new API key. Returns the raw key (shown once)."""
    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)
    conn = get_sync_connection()
    try:
        conn.execute(
            "INSERT INTO api_keys (key_hash, label) VALUES (?, ?)",
            (key_hash, label),
        )
        conn.commit()
        return {"key": raw_key, "label": label}
    finally:
        conn.close()


def validate_api_key(raw_key: str) -> bool:
    """Validate an API key against stored hashes."""
    key_hash = hash_api_key(raw_key)
    conn = get_sync_connection()
    try:
        cursor = conn.execute(
            "SELECT id FROM api_keys WHERE key_hash = ? AND is_active = 1",
            (key_hash,),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()
