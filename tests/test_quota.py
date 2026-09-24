import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.quota import QuotaService


def test_guest_question_quota_blocks_after_limit():
    async def scenario():
        service = QuotaService(MagicMock())
        service._increment = AsyncMock(side_effect=[5, 6])

        first = await service.check_request("guest-a", ["guest"])
        second = await service.check_request("guest-a", ["guest"])

        assert first.allowed is True
        assert second.allowed is False
        assert "question" in second.reason

    asyncio.run(scenario())


def test_guest_token_quota_blocks_after_limit():
    async def scenario():
        service = QuotaService(MagicMock())
        service._increment = AsyncMock(side_effect=[19900, 20200])

        first = await service.consume_tokens("guest-a", ["guest"], 100)
        second = await service.consume_tokens("guest-a", ["guest"], 300)

        assert first.allowed is True
        assert second.allowed is False
        assert "token" in second.reason

    asyncio.run(scenario())


def test_authenticated_user_is_unlimited():
    async def scenario():
        service = QuotaService(MagicMock())
        service._increment = AsyncMock()

        decision = await service.check_request("demo", ["user", "admin"])

        assert decision.allowed is True
        assert not service._increment.called

    asyncio.run(scenario())


def test_status_returns_remaining_quota():
    async def scenario():
        service = QuotaService(MagicMock())
        service._read = AsyncMock(side_effect=[2, 500])

        status = await service.status("guest-a", ["guest"])

        assert status.remaining_questions == 3
        assert status.remaining_tokens == 19500
        assert status.authenticated is False

    asyncio.run(scenario())