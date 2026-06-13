"""Password hashing (pure-python PBKDF2) and JWT helpers."""
import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timedelta, timezone

import jwt

from .config import JWT_SECRET, JWT_ALG, JWT_TTL_MIN

_ITER = 120_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITER)
    return f"pbkdf2_sha256${_ITER}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iters)
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


def create_token(subject: str, kind: str, extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "kind": kind,  # "user" | "admin"
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_TTL_MIN)).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])


def ulid(prefix: str) -> str:
    """A sortable-ish id with a recognizable prefix (agt_, tsk_, ...)."""
    ts = int(time.time() * 1000)
    return f"{prefix}_{ts:012x}{secrets.token_hex(5)}"
