"""
对测试数据库执行 Alembic 迁移（开发环境用）。

测试库 URL 与 tests/conftest.py 一致：由 settings.database_url 派生，
将库名改为 test_ 前缀（如 ai_agent -> test_ai_agent）。

使用方式:
  uv run python scripts/migrate_test_db.py
  或: make db-upgrade-test
"""

import os
import subprocess
import sys


def main() -> int:
    from bootstrap.config import settings

    url = settings.database_url
    parts = url.rsplit("/", maxsplit=1)
    if len(parts) != 2:
        print("ERROR: 无法解析 database_url", file=sys.stderr)
        return 1
    test_url = f"{parts[0]}/test_{parts[1]}"
    env = os.environ.copy()
    env["DATABASE_URL"] = test_url
    print(f"对测试数据库执行迁移: {test_url}")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
