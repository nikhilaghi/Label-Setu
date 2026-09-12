from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import base64
import hashlib
import hmac
import json
import secrets
from app.config import settings

_HASH_PREFIX = "pbkdf2_sha256$"
_ITERATIONS = 180_000

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def _unb64url(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

def get_password_hash(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"{_HASH_PREFIX}{_ITERATIONS}${_b64url(salt)}${_b64url(digest)}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        if not plain_password or not hashed_password or not hashed_password.startswith(_HASH_PREFIX):
            return False
        _, iterations, salt_b64, digest_b64 = hashed_password.split("$", 3)
        salt = _unb64url(salt_b64)
        expected = _unb64url(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", plain_password.encode(), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = dict(data)
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=settings.JWT_EXPIRATION_HOURS))
    payload["exp"] = int(expire.timestamp())
    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()
    signature = hmac.new(settings.JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url(signature)}"

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, signature_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode()
        expected = hmac.new(settings.JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64url(signature_b64)):
            return None
        payload = json.loads(_unb64url(payload_b64).decode())
        if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
            return None
        return payload
    except Exception:
        return None
