from datetime import datetime

from psycopg.types.json import Jsonb


class UserRepository:
    def __init__(self, pool):
        self._pool = pool

    async def create_user(
        self,
        username: str,
        password_hash: str,
        tenant_id: str,
        roles: list[str],
    ) -> dict:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO users
                    (username, password_hash, roles, tenant_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (username) DO NOTHING
                RETURNING
                    id,
                    username,
                    password_hash,
                    roles,
                    tenant_id,
                    created_at
                """,
                (username, password_hash, Jsonb(roles), tenant_id),
            )
            row = await cur.fetchone()

            await conn.commit()

        if row is None:
            raise ValueError("username already exists")

        return self._row_to_dict(row)

    async def get_by_username(self, username: str) -> dict | None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    id,
                    username,
                    password_hash,
                    roles,
                    tenant_id,
                    created_at
                FROM users
                WHERE username = %s
                """,
                (username,),
            )
            row = await cur.fetchone()

        if row is None:
            return None

        return self._row_to_dict(row)

    async def list_users(self) -> list[dict]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    id,
                    username,
                    password_hash,
                    roles,
                    tenant_id,
                    created_at
                FROM users
                ORDER BY id ASC
                """
            )
            rows = await cur.fetchall()

        return [self._row_to_dict(row) for row in rows]

    def _row_to_dict(self, row) -> dict:
        return {
            "id": row[0],
            "username": row[1],
            "password_hash": row[2],
            "roles": list(row[3]),
            "tenant_id": row[4],
            "created_at": self._format_time(row[5]),
        }

    def _format_time(self, value) -> str:
        if isinstance(value, datetime):
            return value.isoformat()

        return str(value)