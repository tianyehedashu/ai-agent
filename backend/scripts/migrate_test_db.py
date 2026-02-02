"""
对测试数据库执行 Alembic 迁移（开发环境用）。

测试库 URL 与 tests/conftest.py 一致：由 settings.database_url 派生，
将库名改为 test_ 前缀（如 ai_agent -> test_ai_agent）。

使用方式:
  uv run python scripts/migrate_test_db.py
  uv run python scripts/migrate_test_db.py --reset   # 先清空测试库再迁移（解决表已存在冲突）
  或: make db-upgrade-test
  或: make db-reset-test   # 清空测试库并迁移
"""

import argparse
import asyncio
import os
from pathlib import Path
import subprocess
import sys


def _get_test_url() -> str:
    from bootstrap.config import settings

    url = settings.database_url
    parts = url.rsplit("/", maxsplit=1)
    if len(parts) != 2:
        raise ValueError("无法解析 database_url")
    return f"{parts[0]}/test_{parts[1]}"


async def _reset_test_db(test_url: str) -> None:
    """清空测试库：DROP SCHEMA public CASCADE 并重建，便于从零执行迁移。"""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(test_url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE;"))
            await conn.execute(text("CREATE SCHEMA public;"))
            await conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
    finally:
        await engine.dispose()
    print("已清空测试库 public schema。")


def main() -> int:
    parser = argparse.ArgumentParser(description="对测试数据库执行 Alembic 迁移")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="先清空测试库（DROP SCHEMA public CASCADE）再执行迁移，用于解决「表已存在」等冲突",
    )
    args = parser.parse_args()

    try:
        test_url = _get_test_url()
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env["DATABASE_URL"] = test_url
    backend_dir = str(Path(__file__).resolve().parent.parent)

    if args.reset:
        print(f"对测试数据库执行迁移（--reset）: {test_url}")
        try:
            asyncio.run(_reset_test_db(test_url))
        except Exception as e:
            print(f"ERROR: 清空测试库失败: {e}", file=sys.stderr)
            return 1
    else:
        print(f"对测试数据库执行迁移: {test_url}")

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        cwd=backend_dir,
    )
    if result.returncode != 0 and not args.reset:
        print(
            "\n若因「relation already exists」等冲突失败，可先清空测试库再迁移：",
            file=sys.stderr,
        )
        print("  uv run python scripts/migrate_test_db.py --reset", file=sys.stderr)
        print("  或: make db-reset-test", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
