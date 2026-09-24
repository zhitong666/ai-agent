from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from app.config import get_settings

QUOTA_INCRBY_SCRIPT = """
local key = KEYS[1]
local amount = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local current = redis.call('INCRBY', key, amount)
if current == amount then
    redis.call('EXPIRE', key, ttl)
end
return current
"""


class QuotaStatus(BaseModel):
    identity: str = Field(..., min_length=1)
    roles: list[str] = Field(default_factory=list)
    authenticated: bool = False
    question_limit: int
    token_limit: int
    used_questions: int
    used_tokens: int
    remaining_questions: int | None = None
    remaining_tokens: int | None = None
    reset_at: datetime | None = None


class QuotaDecision(BaseModel):
    allowed: bool
    reason: str = ""


class QuotaService:
    """Redis-backed daily quota for guest and authenticated users."""

    def __init__(self, redis):
        self._redis = redis

    def _timezone(self):
        return ZoneInfo(get_settings().quota_timezone)

    def _today(self):
        return datetime.now(self._timezone()).date()

    def _reset_at(self):
        today = self._today()
        next_day = datetime(
            today.year,
            today.month,
            today.day,
            tzinfo=self._timezone(),
        ) + timedelta(days=1)
        return next_day.astimezone(UTC)

    def _ttl_seconds(self):
        reset_at = self._reset_at()
        return max(60, int((reset_at - datetime.now(UTC)).total_seconds()) + 60)

    def _key(self, subject: str, metric: str):
        return f"quota:{subject}:{self._today().isoformat()}:{metric}"

    def _limits(self, roles: list[str]):
        settings = get_settings()

        if "guest" in roles:
            return (
                settings.guest_daily_questions,
                settings.guest_daily_tokens,
            )

        return (
            settings.authenticated_daily_questions,
            settings.authenticated_daily_tokens,
        )

    async def _increment(self, key: str, amount: int) -> int:
        value = await self._redis.eval(
            QUOTA_INCRBY_SCRIPT,
            1,
            key,
            amount,
            self._ttl_seconds(),
        )
        return int(value)

    async def _read(self, key: str) -> int:
        value = await self._redis.get(key)
        return int(value) if value is not None else 0

    async def check_request(self, subject: str, roles: list[str]) -> QuotaDecision:
        question_limit, _ = self._limits(roles)

        if question_limit <= 0:
            return QuotaDecision(allowed=True)

        current = await self._increment(
            self._key(subject, "questions"),
            1,
        )

        if current <= question_limit:
            return QuotaDecision(allowed=True)

        return QuotaDecision(
            allowed=False,
            reason="daily question quota exceeded",
        )

    async def consume_tokens(
        self,
        subject: str,
        roles: list[str],
        amount: int,
    ) -> QuotaDecision:
        _, token_limit = self._limits(roles)

        if token_limit <= 0:
            return QuotaDecision(allowed=True)

        current = await self._increment(
            self._key(subject, "tokens"),
            max(1, int(amount)),
        )

        if current <= token_limit:
            return QuotaDecision(allowed=True)

        return QuotaDecision(
            allowed=False,
            reason="daily token quota exceeded",
        )

    async def status(self, subject: str, roles: list[str]) -> QuotaStatus:
        question_limit, token_limit = self._limits(roles)
        used_questions = await self._read(
            self._key(subject, "questions"),
        )
        used_tokens = await self._read(
            self._key(subject, "tokens"),
        )

        return QuotaStatus(
            identity=subject,
            roles=roles,
            authenticated="guest" not in roles,
            question_limit=question_limit,
            token_limit=token_limit,
            used_questions=used_questions,
            used_tokens=used_tokens,
            remaining_questions=(
                max(0, question_limit - used_questions)
                if question_limit > 0
                else None
            ),
            remaining_tokens=(
                max(0, token_limit - used_tokens)
                if token_limit > 0
                else None
            ),
            reset_at=self._reset_at(),
        )
