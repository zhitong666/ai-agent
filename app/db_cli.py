import argparse
import asyncio
from pathlib import Path

from app.postgres import create_postgres_pool

MIGRATIONS_DIR = Path("migrations")

SCHEMA_MIGRATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def _load_statements(path: Path) -> list[str]:
    sql = path.read_text(encoding="utf-8")
    statements = []

    for raw in sql.split(";"):
        statement = raw.strip()

        if not statement or statement.startswith("--"):
            continue

        statements.append(statement)

    return statements


async def _migration_applied(pool, version: str) -> bool:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT 1
                FROM schema_migrations
                WHERE version = %s
                """,
            (version,),
        )
        row = await cur.fetchone()

    return row is not None


async def run_migrations(pool) -> None:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(SCHEMA_MIGRATIONS_TABLE_SQL)
        await conn.commit()

    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = path.stem

        if await _migration_applied(pool, version):
            continue

        statements = _load_statements(path)

        async with pool.connection() as conn, conn.cursor() as cur:
            try:
                for statement in statements:
                    await cur.execute(statement)

                await cur.execute(
                    """
                    INSERT INTO schema_migrations (version)
                    VALUES (%s)
                    """,
                    (version,),
                )

                await conn.commit()
            except Exception:
                await conn.rollback()
                raise


async def check_database(pool) -> bool:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT 1")
        row = await cur.fetchone()

    return row is not None


async def main() -> None:
    parser = argparse.ArgumentParser(description="PostgreSQL 数据库工具")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("migrate")
    subparsers.add_parser("check")

    args = parser.parse_args()

    if args.command == "migrate":
        pool = await create_postgres_pool()
        try:
            await run_migrations(pool)
            print("migrations applied")
        finally:
            await pool.close()

    elif args.command == "check":
        pool = await create_postgres_pool()
        try:
            ok = await check_database(pool)
            print("database ok" if ok else "database unavailable")
        finally:
            await pool.close()

    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())