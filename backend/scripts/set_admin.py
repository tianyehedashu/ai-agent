"""
设置用户为管理员

使用方法:
    # 通过邮箱设置管理员
    uv run python scripts/set_admin.py --email denglietao@qq.com

    # 列出所有用户
    uv run python scripts/set_admin.py --list

    # 取消管理员权限
    uv run python scripts/set_admin.py --email denglietao@qq.com --revoke
"""

import argparse
import asyncio
from pathlib import Path
import sys

# 添加项目根目录到 Python 路径（必须在导入项目模块之前）
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text  # pylint: disable=wrong-import-position
from sqlalchemy.ext.asyncio import (  # pylint: disable=wrong-import-position
    AsyncSession,
    create_async_engine,
)

from bootstrap.config_loader import get_app_config  # pylint: disable=wrong-import-position


async def get_engine():
    """获取数据库引擎"""
    config = get_app_config()
    return create_async_engine(config.infra.database_url, echo=False)


async def list_users():
    """列出所有用户"""
    engine = await get_engine()
    async with AsyncSession(engine) as session:
        result = await session.execute(
            text("SELECT id, email, name, role, is_active FROM users ORDER BY created_at DESC")
        )
        users = result.fetchall()

        if not users:
            print("没有找到任何用户")
            await engine.dispose()
            return

        print("\n用户列表:")
        print("-" * 100)
        print(f"{'ID':<40} {'邮箱':<30} {'名称':<15} {'角色':<10} {'状态'}")
        print("-" * 100)
        for user in users:
            user_id, email, name, role, is_active = user
            status = "活跃" if is_active else "禁用"
            name = name or "-"
            print(f"{user_id!s:<40} {email:<30} {name:<15} {role:<10} {status}")
        print("-" * 100)
        print(f"共 {len(users)} 个用户\n")

    await engine.dispose()


async def set_admin(email: str, revoke: bool = False):
    """设置或撤销管理员权限"""
    engine = await get_engine()
    async with AsyncSession(engine) as session:
        # 查找用户
        result = await session.execute(
            text("SELECT id, email, name, role FROM users WHERE email = :email"), {"email": email}
        )
        user = result.fetchone()

        if not user:
            print(f"错误: 未找到邮箱为 '{email}' 的用户")
            await engine.dispose()
            return False

        user_id, _, user_name, current_role = user
        new_role = "user" if revoke else "admin"
        action = "撤销管理员权限" if revoke else "设置为管理员"

        if current_role == new_role:
            print(f"用户 '{email}' 已经是 '{new_role}' 角色，无需更改")
            await engine.dispose()
            return True

        # 更新角色
        await session.execute(
            text("UPDATE users SET role = :role WHERE id = :id"), {"role": new_role, "id": user_id}
        )
        await session.commit()

        print(f"成功: 已将用户 '{email}' {action}")
        print(f"  - 用户ID: {user_id}")
        print(f"  - 用户名: {user_name or '-'}")
        print(f"  - 原角色: {current_role}")
        print(f"  - 新角色: {new_role}")

    await engine.dispose()
    return True


def main():
    parser = argparse.ArgumentParser(description="管理员权限设置工具")
    parser.add_argument("--email", "-e", help="用户邮箱")
    parser.add_argument("--list", "-l", action="store_true", help="列出所有用户")
    parser.add_argument("--revoke", "-r", action="store_true", help="撤销管理员权限")

    args = parser.parse_args()

    if args.list:
        asyncio.run(list_users())
    elif args.email:
        asyncio.run(set_admin(args.email, args.revoke))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
