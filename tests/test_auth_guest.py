import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx

from app.auth_security import decode_access_token
from app.main import app
from app.quota import QuotaStatus


def seed_state():
    app.state.rate_limiter = MagicMock()
    app.state.rate_limiter.allow = AsyncMock(return_value=True)
    app.state.quota_service = MagicMock()
    app.state.quota_service.status = AsyncMock(
        return_value=QuotaStatus(
            identity="guest:test",
            roles=["guest"],
            authenticated=False,
            question_limit=5,
            token_limit=20000,
            used_questions=0,
            used_tokens=0,
            remaining_questions=5,
            remaining_tokens=20000,
        )
    )


def test_guest_session_and_quota_endpoint():
    async def scenario():
        seed_state()

        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post("/auth/guest")

            assert response.status_code == 200
            token = response.json()["access_token"]
            payload = decode_access_token(token)
            assert payload["roles"] == ["guest"]

            quota_response = await client.get(
                "/auth/quota",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert quota_response.status_code == 200
            assert quota_response.json()["authenticated"] is False

    asyncio.run(scenario())


def test_registration_is_disabled_by_default():
    async def scenario():
        seed_state()

        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/auth/register",
                json={
                    "username": "new-user",
                    "password": "password123",
                },
            )

        assert response.status_code == 403

    asyncio.run(scenario())