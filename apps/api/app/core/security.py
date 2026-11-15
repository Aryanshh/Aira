import os
import sys
import hashlib
import random
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

from app.config import settings
from app.core.time import utc_now


_test_hasher = PasswordHasher(
    time_cost=1,
    memory_cost=1024,
    parallelism=1,
    hash_len=16,
    salt_len=8,
)

_prod_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def _get_ph() -> PasswordHasher:
    if (
        settings.APP_ENV == "test"
        or "pytest" in sys.modules
        or os.environ.get("APP_ENV") == "test"
    ):
        return _test_hasher
    return _prod_hasher


def hash_password(password: str) -> str:
    """Hash a password using Argon2id."""
    return _get_ph().hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify an Argon2id password hash."""
    try:
        return _get_ph().verify(hashed_password, plain_password)
    except (VerificationError, VerifyMismatchError):
        return False


def hash_pin(pin: str) -> str:
    """Hash an elder 4-digit PIN using Argon2id."""
    return _get_ph().hash(pin)


def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
    """Verify an elder 4-digit PIN."""
    try:
        return _get_ph().verify(hashed_pin, plain_pin)
    except (VerificationError, VerifyMismatchError):
        return False


def hash_token(token: str) -> str:
    """SHA-256 hash for database storage of refresh, QR, or single-use tokens."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_random_token(length: int = 32) -> str:
    """Generate a cryptographically secure URL-safe random string."""
    return secrets.token_urlsafe(length)


def generate_elder_access_code() -> str:
    """Generate an elder access code like AIRA-7K3Q (excluding 0, O, 1, I)."""
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    suffix = "".join(secrets.choice(alphabet) for _ in range(4))
    return f"AIRA-{suffix}"


def generate_elder_pin() -> str:
    """Generate a 4-digit numeric PIN."""
    return f"{secrets.randbelow(10000):04d}"


def create_access_token(
    subject: str,
    claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token (default 15 minutes)."""
    if expires_delta:
        expire = utc_now() + expires_delta
    else:
        expire = utc_now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode: Dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": utc_now(),
        "type": "access",
    }
    if claims:
        to_encode.update(claims)

    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a signed JWT access token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.PyJWTError as e:
        raise ValueError(f"Invalid or expired token: {str(e)}")
