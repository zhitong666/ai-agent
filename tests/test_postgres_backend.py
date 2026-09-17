import asyncio
import os
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db_cli import run_migrations
from app.postgres import create_postgres_pool
from app.postgres_session_store import PostgresSessionStore


class AsyncContextManager:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, tb):
        return False


def make_pool():
    pool = MagicMock()
    conn = MagicMock()
    cur = AsyncMock()

    pool.connection.return_value = AsyncContextManager(conn)
    conn.cursor.return_value = AsyncContextManager(cur)
    conn.commit = AsyncMock()
    conn.rollback = AsyncMock()

    return pool, conn, cur


def test_get_messages_returns_chat_history():
    async def scenario():
        pool, _conn, cur = make_pool()
        cur.fetchall.return_value = [
            ("user", "你好"),
            ("assistant", "你好，有什么可以帮你"),
        ]

        store = PostgresSessionStore(pool)
        messages = await store.get_messages("s1")

        assert messages == [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好，有什么可以帮你"},
        ]

        sql = cur.execute.await_args.args[0]
        assert "FROM chat_messages" in sql
        assert "ORDER BY id ASC" in sql

    asyncio.run(scenario())


def test_append_turn_writes_user_and_assistant_in_one_transaction():
    async def scenario():
        pool, conn, cur = make_pool()

        store = PostgresSessionStore(pool)
        await store.append_turn("s1", "什么是 RAG", "RAG 是检索增强生成")

        assert cur.execute.await_count == 2
        assert conn.commit.await_count == 1
        assert conn.rollback.await_count == 0

        insert_sqls = [
            call.args[0]
            for call in cur.execute.await_args_list
        ]
        assert sum("INSERT INTO chat_messages" in sql for sql in insert_sqls) == 2

    asyncio.run(scenario())


def test_append_turn_rolls_back_when_second_insert_fails():
    async def scenario():
        pool, conn, cur = make_pool()
        cur.execute.side_effect = [None, RuntimeError("database insert failed")]

        store = PostgresSessionStore(pool)

        with pytest.raises(RuntimeError, match="database insert failed"):
            await store.append_turn("s1", "问题", "答案")

        assert conn.rollback.await_count == 1
        assert conn.commit.await_count == 0

    asyncio.run(scenario())


def test_postgres_roundtrip_requires_test_database():
    dsn = os.getenv("TEST_DATABASE_URL")

    if not dsn:
        pytest.skip("TEST_DATABASE_URL not set")

    async def scenario():
        pool = await create_postgres_pool(dsn)
        await run_migrations(pool)

        store = PostgresSessionStore(pool)
        session_id = f"integration-{uuid.uuid4().hex}"

        await store.append_turn(session_id, "你好", "你好")
        messages = await store.get_messages(session_id)

        assert messages == [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好"},
        ]

        await pool.close()

    asyncio.run(scenario())