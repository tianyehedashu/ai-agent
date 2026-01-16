"""
修复数据库表结构
统一修复所有继承 BaseModel 的表，确保它们都有 created_at 和 updated_at 字段
"""

import asyncio
from pathlib import Path
import sys

# 添加项目根目录到路径（必须在导入项目模块之前）
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入必须在 sys.path 修改之后，使用 # pylint: disable=wrong-import-position 抑制警告
from sqlalchemy import text  # pylint: disable=wrong-import-position

from db.database import close_db, get_engine, init_db  # pylint: disable=wrong-import-position

# 所有继承 BaseModel 的表
BASEMODEL_TABLES = [
    "users",
    "agents",
    "sessions",
    "messages",
    "memories",
]


async def check_and_fix_updated_at_fields(conn):
    """检查并修复所有 BaseModel 表的 updated_at 字段"""
    print("=" * 60)
    print("检查所有 BaseModel 表的 updated_at 字段...")
    for table_name in BASEMODEL_TABLES:
        result = await conn.execute(
            text(
                f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = '{table_name}' AND column_name = 'updated_at'
            """
            )
        )
        has_updated_at = result.fetchone() is not None
        if not has_updated_at:
            print(f"  - {table_name}: 缺少 updated_at，正在添加...")
            await conn.execute(
                text(
                    f"""
                    ALTER TABLE {table_name}
                    ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP;
                """
                )
            )
            print(f"    ✓ {table_name}.updated_at 已添加")
        else:
            print(f"  - {table_name}: updated_at 已存在 ✓")


async def check_sessions_table_columns(conn):
    """检查 sessions 表的列并返回列信息"""
    print("\n" + "=" * 60)
    print("检查 sessions 表...")
    result = await conn.execute(
        text(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'sessions'
            ORDER BY ordinal_position
        """
        )
    )
    columns = result.fetchall()
    print("当前 sessions 表的列：")
    for col in columns:
        print(f"  - {col[0]}: {col[1]} (nullable: {col[2]}, default: {col[3]})")

    has_metadata = any(col[0] == "metadata" for col in columns)
    has_context = any(col[0] == "context" for col in columns)
    has_status = any(col[0] == "status" for col in columns)
    has_is_active = any(col[0] == "is_active" for col in columns)

    print("\n检查结果：")
    print(f"  - metadata 列存在: {has_metadata}")
    print(f"  - context 列存在: {has_context}")
    print(f"  - status 列存在: {has_status}")
    print(f"  - is_active 列存在: {has_is_active}")

    return columns, has_metadata, has_context, has_status, has_is_active


async def fix_sessions_metadata_to_context(conn, has_metadata, has_context):
    """修复 sessions 表的 metadata 到 context 的重命名"""
    if has_metadata and not has_context:
        print("\n开始修复：将 metadata 重命名为 context...")
        try:
            await conn.execute(text("DROP INDEX IF EXISTS idx_sessions_metadata_gin"))
            await conn.execute(text("ALTER TABLE sessions RENAME COLUMN metadata TO context"))
            await conn.execute(
                text("ALTER TABLE sessions ALTER COLUMN context SET DEFAULT '{}'::jsonb")
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_sessions_context_gin ON sessions USING GIN (context)"
                )
            )
            print("✓ metadata 已重命名为 context")
            return True
        except Exception as e:
            print(f"✗ 重命名失败: {e}")
            return False
    elif has_metadata and has_context:
        print("\n开始修复：删除重复的 metadata 列（模型已使用 context）...")
        try:
            await conn.execute(
                text(
                    """
                UPDATE sessions
                SET context = COALESCE(context, metadata, '{}'::jsonb)
                WHERE context IS NULL OR context = '{}'::jsonb
            """
                )
            )
            await conn.execute(text("DROP INDEX IF EXISTS idx_sessions_metadata_gin"))
            await conn.execute(text("ALTER TABLE sessions DROP COLUMN metadata"))
            print("✓ metadata 列已删除（已使用 context 列）")
            return True
        except Exception as e:
            print(f"✗ 删除 metadata 失败: {e}")
            return False
    return True


async def fix_sessions_status_column(conn, has_status, has_is_active):
    """修复 sessions 表的 status 列"""
    if not has_status:
        print("\n开始修复：添加 status 列...")
        try:
            if has_is_active:
                await conn.execute(
                    text(
                        """
                    ALTER TABLE sessions ADD COLUMN status VARCHAR(20);
                    UPDATE sessions SET status = CASE
                        WHEN is_active = true THEN 'active'
                        ELSE 'archived'
                    END;
                    ALTER TABLE sessions ALTER COLUMN status SET DEFAULT 'active';
                    ALTER TABLE sessions ALTER COLUMN status SET NOT NULL;
                """
                    )
                )
            else:
                await conn.execute(
                    text(
                        """
                    ALTER TABLE sessions ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active';
                """
                    )
                )
            print("✓ status 列已添加")
        except Exception as e:
            print(f"✗ 添加 status 失败: {e}")


async def fix_sessions_message_count_column(conn, columns):
    """修复 sessions 表的 message_count 列"""
    if not any(col[0] == "message_count" for col in columns):
        print("\n开始修复：添加 message_count 列...")
        try:
            await conn.execute(
                text(
                    """
                ALTER TABLE sessions ADD COLUMN message_count INTEGER;
                UPDATE sessions SET message_count = (
                    SELECT COUNT(*) FROM messages WHERE messages.session_id = sessions.id
                );
                ALTER TABLE sessions ALTER COLUMN message_count SET DEFAULT 0;
                ALTER TABLE sessions ALTER COLUMN message_count SET NOT NULL;
            """
                )
            )
            print("✓ message_count 列已添加")
        except Exception as e:
            print(f"✗ 添加 message_count 失败: {e}")


async def fix_sessions_token_count_column(conn, columns):
    """修复 sessions 表的 token_count 列"""
    if not any(col[0] == "token_count" for col in columns):
        print("\n开始修复：添加 token_count 列...")
        try:
            await conn.execute(
                text(
                    """
                ALTER TABLE sessions ADD COLUMN token_count INTEGER NOT NULL DEFAULT 0;
            """
                )
            )
            print("✓ token_count 列已添加")
        except Exception as e:
            print(f"✗ 添加 token_count 失败: {e}")


async def fix_sessions_remove_is_active(conn, has_is_active, has_status):
    """删除 sessions 表的 is_active 列"""
    if has_is_active and has_status:
        print("\n开始修复：删除 is_active 列...")
        try:
            await conn.execute(text("DROP INDEX IF EXISTS idx_sessions_active"))
            await conn.execute(text("ALTER TABLE sessions DROP COLUMN is_active"))
            print("✓ is_active 列已删除")
        except Exception as e:
            print(f"✗ 删除 is_active 失败: {e}")


async def print_sessions_table_final_state(conn):
    """打印 sessions 表的最终状态"""
    result = await conn.execute(
        text(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'sessions'
            ORDER BY ordinal_position
        """
        )
    )
    columns = result.fetchall()
    print("\n修复后的 sessions 表列：")
    for col in columns:
        print(f"  - {col[0]}: {col[1]} (nullable: {col[2]})")


async def fix_messages_token_count_column(conn):
    """修复 messages 表的 token_count 列"""
    print("\n" + "=" * 60)
    print("检查 messages 表的特殊字段...")
    result = await conn.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'messages' AND column_name = 'token_count'
        """
        )
    )
    has_token_count = result.fetchone() is not None
    if not has_token_count:
        print("添加 token_count 列...")
        try:
            await conn.execute(
                text(
                    """
                ALTER TABLE messages ADD COLUMN token_count INTEGER;
            """
                )
            )
            print("✓ token_count 列已添加")
        except Exception as e:
            print(f"✗ 添加 token_count 失败: {e}")
    else:
        print("✓ token_count 已存在")


async def check_and_fix_all_tables():
    """检查并修复所有继承 BaseModel 的表结构"""
    await init_db()
    engine = get_engine()

    async with engine.begin() as conn:
        await check_and_fix_updated_at_fields(conn)

        (
            columns,
            has_metadata,
            has_context,
            has_status,
            has_is_active,
        ) = await check_sessions_table_columns(conn)

        if not await fix_sessions_metadata_to_context(conn, has_metadata, has_context):
            return

        await fix_sessions_status_column(conn, has_status, has_is_active)
        await fix_sessions_message_count_column(conn, columns)
        await fix_sessions_token_count_column(conn, columns)
        await fix_sessions_remove_is_active(conn, has_is_active, has_status)
        await print_sessions_table_final_state(conn)
        await fix_messages_token_count_column(conn)

    await close_db()
    print("\n✓ 所有修复完成！")


if __name__ == "__main__":
    asyncio.run(check_and_fix_all_tables())
