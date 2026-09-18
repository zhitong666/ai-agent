import os
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("JWT_EXPIRE_MINUTES", "60")
)

password_hasher = PasswordHash.recommended()


def get_secret_key() -> str:
    return os.getenv(
        "JWT_SECRET",
        "dev-secret-change-me-in-production",
    )


# 密码使用 Argon2 哈希，不存明文
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
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    expires_at = now + expires_delta

    payload = {
        "sub": subject, # 保存用户名
        "roles": roles, # 保存角色
        "tenant_id": tenant_id, # 保存租户
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()), # 保存过期时间
    }

    return jwt.encode(payload, get_secret_key(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        get_secret_key(),
        algorithms=[ALGORITHM],
    )