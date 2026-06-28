"""检查数据库表结构"""
import asyncio

from sqlalchemy import text

from libs.db.database import async_session_factory


async def check_tables():
    async with async_session_factory() as session:
        # 获取所有表
        result = await session.execute(
            text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """)
        )
        tables = result.fetchall()
        
        print(f"📊 数据库中共有 {len(tables)} 张表:\n")
        for t in tables:
            print(f"  ✓ {t[0]}")
        
        # 检查 Alembic 迁移版本
        print("\n📌 当前迁移版本:")
        try:
            result = await session.execute(text("SELECT version_num FROM alembic_version"))
            version = result.scalar()
            print(f"  Current version: {version}")
        except Exception as e:
            print(f"  ⚠️  无法读取迁移版本: {e}")


if __name__ == "__main__":
    asyncio.run(check_tables())
