import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.models import MemoryRecord


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SharedMemoryStore:
    def __init__(self, db_path: str | Path):
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            str(db_path),
            check_same_thread=False,
        )

        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_memory (
                memory_id TEXT PRIMARY KEY,
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(namespace, key)
            )
            """
        )
        self._conn.commit()

    def set(self, namespace: str, key: str, value) -> MemoryRecord:
        now = _now()
        value_json = json.dumps(value, ensure_ascii=False)

        with self._lock:
            existing = self._conn.execute(
                """
                SELECT memory_id, created_at
                FROM agent_memory
                WHERE namespace = ? AND key = ?
                """,
                (namespace, key),
            ).fetchone()

            if existing is None:
                memory_id = uuid.uuid4().hex
                self._conn.execute(
                    """
                    INSERT INTO agent_memory
                        (memory_id, namespace, key, value, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (memory_id, namespace, key, value_json, now, now),
                )
            else:
                memory_id = existing[0]
                created_at = existing[1]
                self._conn.execute(
                    """
                    UPDATE agent_memory
                    SET value = ?, updated_at = ?
                    WHERE memory_id = ?
                    """,
                    (value_json, now, memory_id),
                )

            self._conn.commit()

            return MemoryRecord(
                memory_id=memory_id,
                namespace=namespace,
                key=key,
                value=value,
                created_at=created_at if existing else now,
                updated_at=now,
            )

    def get(self, namespace: str, key: str) -> MemoryRecord | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT memory_id, namespace, key, value, created_at, updated_at
                FROM agent_memory
                WHERE namespace = ? AND key = ?
                """,
                (namespace, key),
            ).fetchone()

        if row is None:
            return None

        return MemoryRecord(
            memory_id=row[0],
            namespace=row[1],
            key=row[2],
            value=json.loads(row[3]),
            created_at=row[4],
            updated_at=row[5],
        )

    def list_namespace(self, namespace: str) -> list[MemoryRecord]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT memory_id, namespace, key, value, created_at, updated_at
                FROM agent_memory
                WHERE namespace = ?
                ORDER BY updated_at DESC
                """,
                (namespace,),
            ).fetchall()

        return [
            MemoryRecord(
                memory_id=row[0],
                namespace=row[1],
                key=row[2],
                value=json.loads(row[3]),
                created_at=row[4],
                updated_at=row[5],
            )
            for row in rows
        ]

    def delete(self, namespace: str, key: str) -> bool:
        with self._lock:
            cursor = self._conn.execute(
                """
                DELETE FROM agent_memory
                WHERE namespace = ? AND key = ?
                """,
                (namespace, key),
            )
            self._conn.commit()

        return cursor.rowcount > 0

    def close(self) -> None:
        self._conn.close()