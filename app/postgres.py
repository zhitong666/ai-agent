import os

from psycopg_pool import AsyncConnectionPool

DEFAULT_DATABASE_URL = (
    "postgresql://ai_agent:ai_agent@localhost:5432/ai_job_agent"
)


def build_database_dsn() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


# AsyncConnectionPool 不是每来一个请求就新建数据库连接，它维护一组可复用连接
# 连接池避免高并发时反复建连和断连
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