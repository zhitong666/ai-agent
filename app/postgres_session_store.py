class PostgresSessionStore:
    def __init__(self, pool):
        self._pool = pool

    async def get_messages(self, session_id: str) -> list[dict]:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                    SELECT role, content
                    FROM chat_messages
                    WHERE session_id = %s
                    ORDER BY id ASC
                    """,
                (session_id,),
            )
            rows = await cur.fetchall()

        return [
            {"role": role, "content": content}
            for role, content in rows
        ]

    async def append_turn(
        self,
        session_id: str,
        question: str,
        answer: str,
    ) -> None:
        async with self._pool.connection() as conn, conn.cursor() as cur:
            try:
                await cur.execute(
                    """
                    INSERT INTO chat_messages
                        (session_id, role, content)
                    VALUES (%s, 'user', %s)
                    """,
                    (session_id, question),
                )
                await cur.execute(
                    """
                    INSERT INTO chat_messages
                        (session_id, role, content)
                    VALUES (%s, 'assistant', %s)
                    """,
                    (session_id, answer),
                )

                await conn.commit()
            except Exception:
                await conn.rollback()
                raise