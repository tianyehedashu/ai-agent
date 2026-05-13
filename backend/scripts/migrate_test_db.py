"""
对测试数据库执行 Alembic 迁移（开发环境用）。

测试库 URL 与 tests/conftest.py 一致：由 settings.database_url 派生，
将库名改为 test_ 前缀（如 ai_agent -> test_ai_agent）。

默认行为：先直接执行迁移；若因「表已存在」等冲突失败，自动清空测试库后重试一次，
无需手动加 --reset。

使用方式:
  uv run python scripts/migrate_test_db.py   # 迁移，冲突时自动清空并重试
  uv run python scripts/migrate_test_db.py --reset   # 强制先清空再迁移
  或: make db-upgrade-test
  或: make db-reset-test
"""

import argparse
import asyncio
import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from bootstrap.config import settings


def _get_test_url() -> str:
    url = settings.database_url
    parts = url.rsplit("/", maxsplit=1)
    if len(parts) != 2:
        raise ValueError("无法解析 database_url")
    return f"{parts[0]}/test_{parts[1]}"


async def _reset_test_db(test_url: str) -> None:
    """清空测试库：DROP SCHEMA public CASCADE 并重建，便于从零执行迁移。"""
    engine = create_async_engine(test_url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE;"))
            await conn.execute(text("CREATE SCHEMA public;"))
            await conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
    finally:
        await engine.dispose()
    print("已清空测试库 public schema。")


def _run_alembic_upgrade(
    env: dict[str, str], cwd: str, capture: bool = False
) -> subprocess.CompletedProcess:
    """执行 alembic upgrade head，capture=True 时捕获输出用于判断是否需 reset。"""
    return subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        cwd=cwd,
        capture_output=capture,
        text=True,
        check=False,
    )


def _is_conflict_error(result: subprocess.CompletedProcess) -> bool:
    """是否为「表/关系已存在」类冲突（可通过 reset 解决）。"""
    out = (result.stderr or "") + (result.stdout or "")
    return "already exists" in out or "DuplicateTable" in out or "DuplicateObject" in out


def main() -> int:
    parser = argparse.ArgumentParser(description="对测试数据库执行 Alembic 迁移")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="强制先清空测试库再执行迁移（跳过首次直接迁移）",
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

    # 默认先捕获输出，以便失败时判断是否为「表已存在」并自动 reset 重试
    result = _run_alembic_upgrade(env, backend_dir, capture=not args.reset)
    if result.returncode == 0:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        return 0

    # 未加 --reset 且失败原因像是「表已存在」时，自动清空并重试一次
    if not args.reset and _is_conflict_error(result):
        print("检测到「表已存在」冲突，自动清空测试库并重试...", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        try:
            asyncio.run(_reset_test_db(test_url))
        except Exception as e:
            print(f"ERROR: 清空测试库失败: {e}", file=sys.stderr)
            return 1
        result = _run_alembic_upgrade(env, backend_dir, capture=False)
        if result.returncode == 0:
            return 0

    if getattr(result, "stderr", None):
        print(result.stderr, file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
