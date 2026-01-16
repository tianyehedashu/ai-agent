"""
Database Connection Management

使用 SQLAlchemy 2.0 异步模式
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import exc as sa_exc
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy 模型基类"""

    pass


# 全局引擎和会话工厂
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    """初始化数据库连接"""
    global _engine, _session_factory

    _engine = create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
    )

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def close_db() -> None:
    """关闭数据库连接"""
    global _engine, _session_factory

    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def get_engine() -> AsyncEngine:
    """获取数据库引擎"""
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取会话工厂"""
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话 (用于 FastAPI 依赖注入)

    SQLAlchemy 的异步会话上下文管理器会自动处理：
    - 异常时自动回滚
    - 正常结束时自动提交
    - 会话关闭和资源清理
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            try:
                await session.commit()
            except sa_exc.PendingRollbackError as e:
                await session.rollback()
                if e.__cause__ is not None:
                    raise e.__cause__ from None  # pylint: disable=raising-non-exception
                raise
        except Exception:
            await session.rollback()
            raise
        # 上下文管理器会自动关闭会话，无需手动处理


@asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话上下文管理器

    用于非 FastAPI 依赖注入的场景（如后台任务、脚本等）
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            try:
                await session.commit()
            except sa_exc.PendingRollbackError as e:
                await session.rollback()
                if e.__cause__ is not None:
                    raise e.__cause__ from None  # pylint: disable=raising-non-exception
                raise
        except Exception:
            await session.rollback()
            raise


# 别名，用于兼容性
get_async_session = get_session_context
get_db_session = get_session_context


async def create_tables() -> None:
    """创建所有表 (仅用于开发/测试)"""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables() -> None:
    """删除所有表 (仅用于开发/测试)"""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
