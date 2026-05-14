"""
Database Connection Management

使用 SQLAlchemy 2.0 异步模式
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from sqlalchemy import event
from sqlalchemy import exc as sa_exc
from sqlalchemy.engine.interfaces import ExceptionContext
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session

from bootstrap.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy 模型基类"""

    pass


# 全局引擎和会话工厂
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


# 触发 pool 回收的 asyncpg 异常文本片段（这些场景说明连接已脏，无法再复用）。
# 当 pool_pre_ping 或正常查询遇到这些错误时，应判为 disconnect 让 pool 重建连接，
# 而不是把 500 抛到应用层。
_ASYNCPG_DIRTY_CONNECTION_MARKERS: tuple[str, ...] = (
    # 任务在事务中途被取消（常见于 SSE 流被前端断开），连接被还回 pool 后
    # 下次 pool_pre_ping 调 connection.transaction().start() 会撞上协议层
    # 仍处于事务状态，asyncpg 抛 InterfaceError。SQLAlchemy 自带的
    # ``is_disconnect`` 不识别这一串，需要我们显式标记。
    "cannot use Connection.transaction() in a manually started transaction",
    # asyncpg 在协议层进入不一致状态后再次使用会报 "another operation is in progress"，
    # 同样表示连接不可复用。
    "another operation is in progress",
)
_SESSION_HAS_WRITES_KEY = "_ai_agent_has_writes"


@event.listens_for(Session, "before_flush")
def _mark_session_has_writes(
    session: Session,
    _flush_context: object,
    _instances: object,
) -> None:
    """标记本事务做过 ORM 写入，避免 flush 后 new/dirty/deleted 被清空而误判。"""
    if session.new or session.dirty or session.deleted:
        session.info[_SESSION_HAS_WRITES_KEY] = True


def _is_dirty_connection_error(exc: BaseException) -> bool:
    """判断异常链里是否包含 asyncpg 脏连接特征。"""
    pending: list[BaseException] = [exc]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        ident = id(current)
        if ident in seen:
            continue
        seen.add(ident)
        message = str(current)
        if any(marker in message for marker in _ASYNCPG_DIRTY_CONNECTION_MARKERS):
            return True
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
    return False


def _session_has_writes(session: AsyncSession) -> bool:
    """判断 FastAPI 请求依赖中的 session 是否需要提交。"""
    sync_session = session.sync_session
    return bool(
        sync_session.info.get(_SESSION_HAS_WRITES_KEY)
        or sync_session.new
        or sync_session.dirty
        or sync_session.deleted
    )


async def _invalidate_if_dirty_connection(
    session: AsyncSession,
    exc: BaseException,
) -> bool:
    """遇到 asyncpg 协议脏连接时失效当前 session 连接，防止坏连接回池。"""
    if not _is_dirty_connection_error(exc):
        return False
    with suppress(Exception):
        await session.invalidate()
    return True


async def _rollback_for_cleanup(session: AsyncSession) -> None:
    """清理请求事务；脏连接回滚失败时失效连接并允许调用方继续返回。"""
    try:
        await session.rollback()
    except Exception as exc:
        if await _invalidate_if_dirty_connection(session, exc):
            return
        raise


async def _commit_or_raise(session: AsyncSession) -> None:
    """提交写事务；提交失败不能静默成功，但要先处理连接失效。"""
    try:
        await session.commit()
    except sa_exc.PendingRollbackError as exc:
        await _rollback_for_cleanup(session)
        if exc.__cause__ is not None:
            raise exc.__cause__ from None  # pylint: disable=raising-non-exception
        raise
    except Exception as exc:
        await _invalidate_if_dirty_connection(session, exc)
        raise


async def _finalize_dependency_session(session: AsyncSession) -> None:
    """FastAPI 依赖退出处理：写事务提交，纯读事务回滚释放连接。"""
    if _session_has_writes(session):
        await _commit_or_raise(session)
        return
    await _rollback_for_cleanup(session)


def _register_dirty_connection_recycle(engine: AsyncEngine) -> None:
    """让 pool_pre_ping 在遇到典型脏连接错误时把连接判为 disconnect 并丢弃。

    背景：``PGDialect_asyncpg.is_disconnect`` 只识别 "connection is closed"，
    不会处理 asyncpg 协议层事务状态被打乱的情况，导致 pool 永远拿到同一条
    坏连接并把异常抛给应用层（500）。这里通过 ``handle_error`` 事件把这些
    错误显式标记为 disconnect，pool 会自动重建连接、重试 ping。
    """

    @event.listens_for(engine.sync_engine, "handle_error")
    def _mark_dirty_connection_as_disconnect(ctx: ExceptionContext) -> None:
        err = ctx.original_exception
        if err is None:
            return
        message = str(err)
        if any(marker in message for marker in _ASYNCPG_DIRTY_CONNECTION_MARKERS):
            ctx.is_disconnect = True


async def init_db() -> None:
    """初始化数据库连接"""
    global _engine, _session_factory

    _engine = create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
        # 周期性回收长时间空闲的连接，进一步降低脏连接概率。
        pool_recycle=300,
    )
    _register_dirty_connection_recycle(_engine)

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

    - 异常或取消时回滚
    - 正常结束时：有 ORM 写入才提交；纯读请求回滚释放事务
    - 脏连接清理失败时主动 invalidate，避免坏连接回池
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await _finalize_dependency_session(session)
        except BaseException:
            await _rollback_for_cleanup(session)
            raise
        # 上下文管理器会自动关闭会话，无需手动处理


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话（FastAPI 依赖注入推荐入口）

    与 get_session 功能相同，作为「规范入口」供路由与 identity 等层使用，
    避免 libs.api.deps 与 identity 的循环导入。
    """
    async for session in get_session():
        yield session


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
            await _commit_or_raise(session)
        except BaseException:
            await _rollback_for_cleanup(session)
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
