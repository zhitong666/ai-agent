import json
from datetime import UTC, datetime


def _now() -> str:
    return datetime.now(UTC).isoformat()


class JobStore:
    def __init__(self, redis, ttl: int = 3600):
        self._redis = redis
        self._ttl = ttl

    def _key(self, job_id: str) -> str:
        return f"job:{job_id}"

    async def create(
        self,
        job_id: str,
        job_type: str,
        payload: dict,
    ) -> dict:
        now = _now()
        mapping = {
            "status": "queued",
            "type": job_type,
            "payload": json.dumps(payload, ensure_ascii=False),
            "result": "",
            "error": "",
            "created_at": now,
            "updated_at": now,
        }

        await self._redis.hset(self._key(job_id), mapping=mapping)
        await self._redis.expire(self._key(job_id), self._ttl)

        return self._as_dict(job_id, mapping)

    async def get(self, job_id: str) -> dict | None:
        raw = await self._redis.hgetall(self._key(job_id))

        if not raw:
            return None

        return self._as_dict(job_id, raw)

    async def mark_running(self, job_id: str) -> None:
        await self._update(job_id, {"status": "running"})

    async def complete(self, job_id: str, result: dict) -> None:
        await self._update(
            job_id,
            {
                "status": "completed",
                "result": json.dumps(result, ensure_ascii=False),
                "error": "",
            },
        )

    async def fail(self, job_id: str, error: str) -> None:
        await self._update(
            job_id,
            {
                "status": "failed",
                "error": error,
            },
        )

    async def _update(self, job_id: str, fields: dict) -> None:
        fields["updated_at"] = _now()
        await self._redis.hset(self._key(job_id), mapping=fields)
        await self._redis.expire(self._key(job_id), self._ttl)

    def _as_dict(self, job_id: str, raw: dict) -> dict:
        return {
            "job_id": job_id,
            "status": raw.get("status", ""),
            "type": raw.get("type", ""),
            "payload": json.loads(raw.get("payload") or "null"),
            "result": json.loads(raw.get("result") or "null"),
            "error": raw.get("error") or None,
            "created_at": raw.get("created_at"),
            "updated_at": raw.get("updated_at"),
        }