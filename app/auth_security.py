from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.config import get_settings


password_hasher = PasswordHash.recommended()


def get_secret_key() -> str:
    return get_settings().jwt_secret.get_secret_value()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(
    subject: str,
    roles: list[str],
    tenant_id: str,
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(UTC)
    expires_delta = expires_delta or timedelta(
        minutes=get_settings().jwt_expire_minutes
    )
    expires_at = now + expires_delta

    payload = {
        "sub": subject,
        "roles": roles,
        "tenant_id": tenant_id,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }

    return jwt.encode(
        payload,
        get_secret_key(),
        algorithm=get_settings().jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        get_secret_key(),
        algorithms=[get_settings().jwt_algorithm],
    )