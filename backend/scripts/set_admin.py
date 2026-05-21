"""
设置用户为平台管理员（bootstrap / 应急）

使用方法:
    # 首个平台 admin（仅当尚无 admin 时）
    uv run python scripts/set_admin.py --email user@example.com

    # 列出所有用户
    uv run python scripts/set_admin.py --list

    # 撤销 admin（至少需 2 名 admin；日常请用设置页）
    uv run python scripts/set_admin.py --email user@example.com --revoke
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from bootstrap.config import settings
from domains.identity.application.user_use_case import UserUseCase
from libs.exceptions import AIAgentError, NotFoundError


async def _session_factory() -> tuple[AsyncSession, object]:
    engine = create_async_engine(settings.database_url, echo=False)
    session = AsyncSession(engine)
    return session, engine


async def list_users() -> None:
    """列出所有用户（运维只读）。"""
    session, engine = await _session_factory()
    try:
        result = await session.execute(
            text(
                "SELECT id, email, name, role, is_active FROM users "
                "ORDER BY created_at DESC"
            )
        )
        users = result.fetchall()
        if not users:
            print("没有找到任何用户")
            return

        print("\n用户列表:")
        print("-" * 100)
        print(f"{'ID':<40} {'邮箱':<30} {'名称':<15} {'角色':<10} {'状态'}")
        print("-" * 100)
        for user_id, email, name, role, is_active in users:
            status = "活跃" if is_active else "禁用"
            print(f"{user_id!s:<40} {email:<30} {name or '-':<15} {role:<10} {status}")
        print("-" * 100)
        print(f"共 {len(users)} 个用户\n")
    finally:
        await session.close()
        await engine.dispose()


async def set_admin(email: str, *, revoke: bool = False) -> bool:
    """通过 UserUseCase + domain policy 设置或撤销平台 admin。"""
    session, engine = await _session_factory()
    try:
        use_case = UserUseCase(session)
        try:
            summary = await use_case.bootstrap_set_admin_by_email(email, revoke=revoke)
        except NotFoundError:
            print(f"错误: 未找到邮箱为 '{email}' 的用户")
            return False
        except AIAgentError as exc:
            print(f"错误: {exc.message}")
            return False

        action = "撤销平台管理员" if revoke else "设置为平台管理员"
        print(f"成功: 已将 {summary.email} {action}")
        print(f"  - 用户ID: {summary.id}")
        print(f"  - 用户名: {summary.name or '-'}")
        print(f"  - 当前角色: {summary.role}")
        await session.commit()
        return True
    finally:
        await session.close()
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="平台管理员 bootstrap 工具")
    parser.add_argument("--email", "-e", help="用户邮箱（不区分大小写）")
    parser.add_argument("--list", "-l", action="store_true", help="列出所有用户")
    parser.add_argument(
        "--revoke",
        "-r",
        action="store_true",
        help="撤销平台 admin（至少 2 名 admin 时可用）",
    )

    args = parser.parse_args()

    if args.list:
        asyncio.run(list_users())
    elif args.email:
        asyncio.run(set_admin(args.email, revoke=args.revoke))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
