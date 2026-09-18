import asyncio
from datetime import timedelta

import httpx
import pytest
from fastapi import HTTPException

from app.auth_dependencies import require_roles
from app.auth_models import TokenPayload
from app.auth_security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.main import app


class FakeUserRepository:
    def __init__(self, user):
        self.user = user

    async def get_by_username(self, username):
        if self.user and self.user["username"] == username:
            return self.user
        return None


def test_password_hash_and_verify():
    password = "secret123"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_create_and_decode_access_token():
    token = create_access_token(
        "alex",
        ["user", "admin"],
        "tenant-a",
        expires_delta=timedelta(minutes=5),
    )

    payload = decode_access_token(token)

    assert payload["sub"] == "alex"
    assert payload["roles"] == ["user", "admin"]
    assert payload["tenant_id"] == "tenant-a"


def test_require_roles_allows_admin():
    async def scenario():
        dependency = require_roles("admin")
        user = TokenPayload(
            sub="alex",
            roles=["admin"],
            tenant_id="tenant-a",
            exp=9999999999,
        )

        result = await dependency(user=user)

        assert result.sub == "alex"

    asyncio.run(scenario())


def test_require_roles_blocks_regular_user():
    async def scenario():
        dependency = require_roles("admin")
        user = TokenPayload(
            sub="alex",
            roles=["user"],
            tenant_id="tenant-a",
            exp=9999999999,
        )

        with pytest.raises(HTTPException) as exc:
            await dependency(user=user)

        assert exc.value.status_code == 403

    asyncio.run(scenario())


def test_login_endpoint_returns_access_token():
    async def scenario():
        password = "secret123"
        password_hash = hash_password(password)

        app.state.user_repository = FakeUserRepository(
            {
                "id": 1,
                "username": "alex",
                "password_hash": password_hash,
                "roles": ["user"],
                "tenant_id": "tenant-a",
            }
        )

        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/auth/login",
                json={"username": "alex", "password": password},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["access_token"]
        assert body["token_type"] == "bearer"

    asyncio.run(scenario())