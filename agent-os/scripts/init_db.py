"""One-shot script: create database + pgvector extension, then run alembic migrations.

Usage (local dev):
    python scripts/init_db.py

Credentials are read from environment variables with defaults matching docker-compose:
    DB_HOST  (default: 127.0.0.1)
    DB_PORT  (default: 5432)
    DB_USER  (default: agentos)
    DB_PASS  (default: agentos)
    DB_NAME  (default: agentos)
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "agentos")
DB_PASS = os.getenv("DB_PASS", "agentos")
DB_NAME = os.getenv("DB_NAME", "agentos")


async def create_database() -> None:
    """连接 postgres 默认库，创建 agentos 数据库（若不存在）。"""
    import asyncpg

    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, database="postgres"
    )
    exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", DB_NAME)
    if exists:
        print(f"[SKIP] Database '{DB_NAME}' already exists.")
    else:
        await conn.execute(f'CREATE DATABASE "{DB_NAME}"')
        print(f"[OK]   Database '{DB_NAME}' created.")
    await conn.close()


async def install_pgvector() -> None:
    """在目标库安装 pgvector 扩展。"""
    import asyncpg

    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, database=DB_NAME
    )
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        print("[OK]   Extension 'vector' installed.")
    except Exception as e:
        print(f"[WARN] pgvector extension skipped: {e}")
    finally:
        await conn.close()


def run_migrations() -> None:
    """调用 alembic 执行所有迁移。"""
    db_url_sync = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    env = {**os.environ, "DATABASE_URL": db_url_sync}
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=str(Path(__file__).resolve().parent.parent),
        env=env,
    )
    if result.returncode != 0:
        print("[ERROR] alembic upgrade head failed.")
        sys.exit(result.returncode)
    print("[OK]   Migrations applied.")


async def main() -> None:
    print("=" * 50)
    print("Agent OS — Database Initialization")
    print("=" * 50)
    print(f"  Host: {DB_HOST}:{DB_PORT}")
    print(f"  User: {DB_USER}")
    print(f"  DB:   {DB_NAME}")
    print()

    print("[1/3] Creating database...")
    await create_database()

    print("\n[2/3] Installing pgvector extension...")
    await install_pgvector()

    print("\n[3/3] Running alembic migrations...")
    run_migrations()

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
