"""Authentication utilities for EdgeCaster local UI."""

from __future__ import annotations

import bcrypt
from itsdangerous import BadSignature, TimestampSigner


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_session_token(secret: str) -> str:
    """Create a signed session token."""
    signer = TimestampSigner(secret)
    return signer.sign("edgecaster-session").decode()


def verify_session_token(token: str, secret: str, max_age_seconds: int = 86400) -> bool:
    """Verify a signed session token. Default max age: 24 hours."""
    signer = TimestampSigner(secret)
    try:
        signer.unsign(token, max_age=max_age_seconds)
        return True
    except BadSignature:
        return False
