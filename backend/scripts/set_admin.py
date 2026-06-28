"""
用户管理 bootstrap 工具（创建用户 + 设置/撤销管理员）

使用方法:
    # 创建用户（若已存在则跳过；--admin 同时设为平台管理员）
    uv run python scripts/set_admin.py --email user@example.com --password Secret123 [--name 名称] [--admin]

    # 列出所有用户
    uv run python scripts/set_admin.py --list

    # 设置为平台 admin（仅当尚无 admin 时；--force 应急提权）
    uv run python scripts/set_admin.py --email user@example.com

    # 撤销 admin（至少需 2 名 admin；日常请用设置页）
    uv run python scripts/set_admin.py --email user@example.com --revoke

    # 应急：已有 admin 时仍提升指定用户
    uv run python scripts/set_admin.py --email user@example.com --force
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv

load_dotenv(BACKEND_ROOT / ".env")

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from bootstrap.config import settings
from domains.identity.application.user_use_case import UserUseCase
from domains.identity.infrastructure.auth.password import hash_password
from domains.identity.infrastructure.default_tenant_lifecycle import (
    provision_default_tenant_for_new_user,
)
from domains.identity.infrastructure.models.user import User
from libs.db.database import close_db, get_session_context, init_db
from libs.db.orm_registry import register_all_orm_models
from libs.exceptions import AIAgentError, NotFoundError
from libs.iam.deps import get_default_tenant_provisioner

register_all_orm_models()


async def _session_factory() -> tuple[AsyncSession, object]:
    engine = create_async_engine(settings.database_url, echo=False)
    session = AsyncSession(engine)
    return session, engine


async def list_users() -> None:
    """列出所有用户（运维只读）。"""
    session, engine = await _session_factory()
    try:
        result = await session.execute(
            text("SELECT id, email, name, role, is_active FROM users ORDER BY created_at DESC")
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


async def create_user(
    email: str,
    password: str,
    name: str | None = None,
    *,
    set_as_admin: bool = False,
) -> User:
    """
    创建用户（若已存在则返回现有用户），自动开通 personal team。

    Args:
        email: 用户邮箱
        password: 明文密码
        name: 显示名称（可选）
        set_as_admin: 同时设为平台管理员
    """
    await init_db()
    try:
        async with get_session_context() as session:
            result = await session.execute(select(User).where(User.email == email))
            existing = result.scalar_one_or_none()

            if existing:
                print(f"⚠️  用户 {email} 已存在 (ID: {existing.id})")
                if set_as_admin and not existing.is_superuser:
                    existing.is_superuser = True
                    existing.role = "admin"
                    await session.flush()
                    print(f"✅ 已升级为平台管理员")
                return existing

            user = User(
                email=email,
                hashed_password=hash_password(password),
                is_active=True,
                is_superuser=set_as_admin,
                is_verified=True,
                name=name or email.split("@")[0],
                role="admin" if set_as_admin else "user",
                status="active",
            )
            session.add(user)
            await session.flush()

            # 开通 personal team（与正常注册流程一致）
            provisioner = get_default_tenant_provisioner()
            await provision_default_tenant_for_new_user(
                session=session,
                provisioner=provisioner,
                user_id=user.id,
                display_name=user.name,
            )

            tag = "（管理员）" if set_as_admin else ""
            print(f"✅ 用户创建成功{tag}")
            print(f"   Email:      {user.email}")
            print(f"   Name:       {user.name}")
            print(f"   ID:         {user.id}")
            print(f"   Superuser:  {user.is_superuser}")
            print(f"   Role:       {user.role}")
            return user
    finally:
        await close_db()


async def set_admin(email: str, *, revoke: bool = False, force: bool = False) -> bool:
    """通过 UserUseCase + domain policy 设置或撤销平台 admin。"""
    await init_db()
    try:
        async with get_session_context() as session:
            use_case = UserUseCase(session)
            try:
                summary = await use_case.bootstrap_set_admin_by_email(
                    email,
                    revoke=revoke,
                    force=force,
                )
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
            return True
    finally:
        await close_db()


def main() -> None:
    parser = argparse.ArgumentParser(description="用户管理 bootstrap 工具（创建用户 / 设置管理员）")
    parser.add_argument("--email", "-e", help="用户邮箱（不区分大小写）")
    parser.add_argument("--password", "-p", help="密码（创建用户时需要，明文传入）")
    parser.add_argument("--name", "-n", help="显示名称（可选）")
    parser.add_argument("--admin", action="store_true", help="创建用户时同时设为平台管理员")
    parser.add_argument("--list", "-l", action="store_true", help="列出所有用户")
    parser.add_argument(
        "--revoke",
        "-r",
        action="store_true",
        help="撤销平台 admin（至少 2 名 admin 时可用）",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="应急提权：已有 admin 时仍将目标用户设为 admin",
    )

    args = parser.parse_args()

    if args.list:
        asyncio.run(list_users())
    elif args.email and args.password:
        # 创建用户模式
        if args.revoke:
            parser.error("--revoke 不能与 --password 同时使用")
        asyncio.run(
            create_user(
                args.email,
                args.password,
                args.name,
                set_as_admin=args.admin,
            )
        )
    elif args.email:
        # 管理员提权 / 撤销模式
        if args.force and args.revoke:
            parser.error("--force 与 --revoke 不能同时使用")
        asyncio.run(set_admin(args.email, revoke=args.revoke, force=args.force))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
