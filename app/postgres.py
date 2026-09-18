from psycopg_pool import AsyncConnectionPool

from app.config import get_settings


def build_database_dsn() -> str:
    return get_settings().database_url


async def create_postgres_pool(
    dsn: str | None = None,
    min_size: int = 1,
    max_size: int = 10,
) -> AsyncConnectionPool:
    pool = AsyncConnectionPool(
        conninfo=dsn or build_database_dsn(),
        min_size=min_size,
        max_size=max_size,
        open=False,
    )

    await pool.open()
    return pool