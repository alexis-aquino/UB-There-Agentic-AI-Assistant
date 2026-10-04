"""Password hashing and session tokens.

Passwords are stored as salted PBKDF2-SHA256. Session tokens are stateless and HMAC-signed:
"<user_id>.<expires_unix>.<signature>", so the server needs no session table.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

PBKDF2_ITERATIONS = 240_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
    )
    return hmac.compare_digest(digest.hex(), digest_hex)


def _sign(payload: str, secret: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode("ascii").rstrip("=")


def issue_token(user_id: int, secret: str, days: int) -> str:
    payload = f"{user_id}.{int(time.time()) + days * 86_400}"
    return f"{payload}.{_sign(payload, secret)}"


def read_token(token: str, secret: str) -> int | None:
    """The user id the token was issued for, or None if it is forged, malformed or expired."""
    try:
        user_id, expires, signature = token.split(".")
        payload = f"{user_id}.{expires}"
        if not hmac.compare_digest(signature, _sign(payload, secret)):
            return None
        if int(expires) < time.time():
            return None
        return int(user_id)
    except ValueError:
        return None
