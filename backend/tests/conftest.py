"""
Pytest Configuration - 测试配置

提供测试所需的 fixtures
"""

import asyncio
from collections.abc import AsyncGenerator, Generator
import contextlib
import logging
import os
import sys
from urllib.parse import urlparse
import uuid
import warnings

import nest_asyncio
import pytest
import pytest_asyncio

# Windows 需要使用 SelectorEventLoop（psycopg 异步要求）
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 配置警告过滤器，抑制第三方库的警告
# 在 pytest 配置之前设置警告过滤器
warnings.filterwarnings("ignore", category=RuntimeWarning, module="litellm")
warnings.filterwarnings(
    "ignore", message=".*coroutine.*was never awaited.*", category=RuntimeWarning
)
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
warnings.filterwarnings("ignore", message=".*PydanticSerializationUnexpectedValue.*")
warnings.filterwarnings(
    "ignore", message=".*enable_cleanup_closed ignored.*", category=DeprecationWarning
)

# 设置环境变量来抑制警告（在解释器关闭时也有效）
# 这些警告在 Python 解释器关闭时产生，pytest 的过滤器无法捕获
if "PYTHONWARNINGS" not in os.environ:
    os.environ["PYTHONWARNINGS"] = "ignore::RuntimeWarning,ignore::UserWarning"


# 使用 pytest 的配置钩子进一步抑制警告
def pytest_configure(config):
    """配置 pytest，抑制第三方库警告"""
    config.addinivalue_line(
        "filterwarnings",
        "ignore::RuntimeWarning:litellm",
    )
    config.addinivalue_line(
        "filterwarnings",
        "ignore:coroutine.*was never awaited:RuntimeWarning",
    )
    config.addinivalue_line(
        "filterwarnings",
        "ignore::UserWarning:pydantic",
    )
    config.addinivalue_line(
        "filterwarnings",
        "ignore:PydanticSerializationUnexpectedValue:UserWarning",
    )
    config.addinivalue_line(
        "filterwarnings",
        "ignore:enable_cleanup_closed ignored:DeprecationWarning:aiohttp",
    )


# 初始化 JWT Manager（在导入测试模块之前）
# 注意：这些导入必须在警告过滤器配置之后（见上方 pytest_configure）
# pylint: disable=wrong-import-position
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from bootstrap.config import settings  # noqa: E402
from domains.agent.infrastructure.models.user_provider_config import (  # noqa: E402
    UserProviderConfig,  # noqa: F401
)
from domains.identity.infrastructure.auth.jwt import init_jwt_manager  # noqa: E402
from domains.identity.infrastructure.models.quota import (  # noqa: E402, F401
    QuotaUsageLog,
    UserQuota,
)
from domains.identity.infrastructure.models.user import User  # noqa: E402
from libs.db.database import Base  # noqa: E402

# pylint: enable=wrong-import-position

# 初始化 JWT Manager 以便测试可以使用便捷函数
init_jwt_manager(settings)

# 测试数据库 URL
TEST_DATABASE_URL = settings.database_url.replace(
    settings.database_url.rsplit("/", maxsplit=1)[-1],
    "test_" + settings.database_url.rsplit("/", maxsplit=1)[-1],
)

# 测试引擎（延迟创建，避免在导入时连接数据库）
test_engine = None
TestAsyncSessionLocal = None

# 标记表是否已创建（进程级别）
_tables_created = False


async def _ensure_test_database():
    """确保测试数据库存在（如果不存在则创建）"""
    # asyncpg 是可选依赖，如果未安装则跳过数据库创建
    import asyncpg  # pylint: disable=import-outside-toplevel

    # 解析数据库 URL
    # 格式: postgresql+asyncpg://user:password@host:port/database
    url_str = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    parsed = urlparse(url_str)

    db_name = parsed.path.lstrip("/")
    if not db_name:
        return  # 无法解析数据库名

    # 构建连接到 postgres 数据库的 URL（用于创建数据库）
    admin_url = f"postgresql://{parsed.netloc}/postgres"

    try:
        conn = await asyncpg.connect(admin_url)
        try:
            # 检查数据库是否存在
            exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
            if not exists:
                # 创建数据库
                await conn.execute(f'CREATE DATABASE "{db_name}"')
        finally:
            await conn.close()
    except Exception as e:
        # 如果创建失败，记录警告但继续（可能是权限问题）
        warnings.warn(
            f"Could not create test database '{db_name}': {e}. "
            f"Please create it manually: CREATE DATABASE {db_name};",
            UserWarning,
            stacklevel=2,
        )


def _create_test_engine():
    """创建测试引擎（延迟创建）"""
    global test_engine, TestAsyncSessionLocal
    if test_engine is None:
        # 先确保数据库存在（在创建引擎之前）
        try:
            # 尝试在现有事件循环中运行，如果没有则创建新的
            try:
                asyncio.get_running_loop()
                # 如果事件循环正在运行，需要特殊处理
                nest_asyncio.apply()
                asyncio.run(_ensure_test_database())
            except RuntimeError:
                # 没有运行的事件循环，直接运行
                asyncio.run(_ensure_test_database())
        except Exception:
            # 如果创建数据库失败，继续尝试连接（可能数据库已存在）
            pass

        try:
            test_engine = create_async_engine(
                TEST_DATABASE_URL,
                poolclass=NullPool,
            )
            TestAsyncSessionLocal = sessionmaker(
                test_engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        except Exception as e:
            # 如果创建失败，设置为 None
            test_engine = None
            TestAsyncSessionLocal = None
            db_name = TEST_DATABASE_URL.rsplit("/", maxsplit=1)[-1]
            raise RuntimeError(
                f"Failed to create test database engine: {e}. "
                f"Please ensure the test database '{db_name}' exists. "
                f"You can create it with: CREATE DATABASE {db_name};"
            ) from e
    return test_engine, TestAsyncSessionLocal


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """数据库会话 fixture

    使用嵌套事务（SAVEPOINT）确保测试完全隔离：
    1. 表结构在进程启动时创建一次（幂等操作）
    2. 每个测试在独立的 SAVEPOINT 中运行
    3. 测试结束后回滚到 SAVEPOINT，数据完全隔离

    这种方式支持并发测试（pytest-xdist），因为：
    - 每个测试使用独立的数据库连接
    - 每个连接有自己的事务和 SAVEPOINT
    - 测试之间完全隔离，不会相互影响

    注意：测试中的 commit() 会被转换为 SAVEPOINT 的 commit，
    不会真正提交到数据库，测试结束后会回滚。
    """
    global _tables_created

    # 先确保测试数据库存在
    with contextlib.suppress(Exception):
        await _ensure_test_database()

    try:
        # 延迟创建测试引擎
        engine, _ = _create_test_engine()
        if engine is None:
            pytest.skip("Database engine creation failed (asyncpg may not be installed)")
    except RuntimeError as e:
        # 如果是数据库不存在的错误，提供更友好的提示
        error_msg = str(e)
        if "does not exist" in error_msg or "InvalidCatalogNameError" in error_msg:
            db_name = TEST_DATABASE_URL.rsplit("/", maxsplit=1)[-1]
            pytest.skip(
                f"Test database '{db_name}' does not exist. "
                f"Please create it manually: CREATE DATABASE {db_name};"
            )
        raise
    except Exception as e:
        pytest.skip(f"Database setup failed: {e}")

    # 确保表存在（幂等操作，多进程安全）
    if not _tables_created:
        async with engine.begin() as conn:
            # create_all 是幂等的，多个进程同时调用也安全
            await conn.run_sync(Base.metadata.create_all)
        _tables_created = True

    # 创建独立的数据库连接
    # 使用 begin() 开始一个事务，然后在其中创建 SAVEPOINT
    connection = await engine.connect()
    transaction = await connection.begin()

    try:
        # 创建会话，绑定到这个连接
        # 使用 begin_nested() 创建 SAVEPOINT，这样测试中的 commit() 不会真正提交
        session = AsyncSession(bind=connection, expire_on_commit=False)

        # 开始嵌套事务（SAVEPOINT）
        nested = await session.begin_nested()

        try:
            yield session
        finally:
            # 无论测试成功还是失败，都回滚 SAVEPOINT
            if nested.is_active:
                await nested.rollback()

            # 关闭会话
            await session.close()
    finally:
        # 回滚外层事务
        await transaction.rollback()
        await connection.close()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP 客户端 fixture"""
    # 延迟导入，避免在导入时触发 lifespan 和循环导入
    # pylint: disable=import-outside-toplevel
    from unittest.mock import AsyncMock, MagicMock, patch

    # Mock init_db 和 init_redis 以避免在测试时初始化
    # 同时 mock get_session_factory 和 get_async_session 以支持直接调用
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("libs.db.database.init_db"),
        patch("libs.db.redis.init_redis"),
        patch("libs.db.database.get_session_factory", return_value=mock_factory),
        patch("libs.db.database.get_async_session", new=mock_factory),
        # 在测试环境中禁用开发模式的匿名用户功能，确保认证测试正常工作
        # patch app_env 属性，这样 is_development property 会返回 False
        patch("bootstrap.config.settings.app_env", "production"),
    ):
        # 这些导入必须在 patch 生效后才能执行
        from bootstrap.main import app  # pylint: disable=import-outside-toplevel
        from domains.agent.infrastructure.engine.langgraph_checkpointer import (
            LangGraphCheckpointer,  # pylint: disable=import-outside-toplevel
        )
        from libs.api.deps import get_db  # pylint: disable=import-outside-toplevel
        from libs.db.database import get_session  # pylint: disable=import-outside-toplevel

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield db_session

        async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_session] = override_get_session

        # 确保 checkpointer 在测试环境中已初始化
        if not hasattr(app.state, "checkpointer"):
            # 在测试环境中使用 MemorySaver（更快，不需要数据库表）
            test_checkpointer = LangGraphCheckpointer(storage_type="memory")
            await test_checkpointer.setup()
            app.state.checkpointer = test_checkpointer

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac

        app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def dev_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """开发模式 HTTP 客户端 fixture（启用匿名用户功能）"""
    # 延迟导入，避免在导入时触发 lifespan 和循环导入
    # pylint: disable=import-outside-toplevel
    from unittest.mock import AsyncMock, MagicMock, patch

    # Mock init_db 和 init_redis 以避免在测试时初始化
    # 同时 mock get_session_factory 和 get_async_session 以支持直接调用
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("libs.db.database.init_db"),
        patch("libs.db.redis.init_redis"),
        patch("libs.db.database.get_session_factory", return_value=mock_factory),
        patch("libs.db.database.get_async_session", new=mock_factory),
        # 保持开发模式以启用匿名用户功能
        patch("bootstrap.config.settings.app_env", "development"),
    ):
        # 这些导入必须在 patch 生效后才能执行
        from bootstrap.main import app  # pylint: disable=import-outside-toplevel
        from domains.agent.infrastructure.engine.langgraph_checkpointer import (
            LangGraphCheckpointer,  # pylint: disable=import-outside-toplevel
        )
        from libs.api.deps import get_db  # pylint: disable=import-outside-toplevel
        from libs.db.database import get_session  # pylint: disable=import-outside-toplevel

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield db_session

        async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_session] = override_get_session

        # 确保 checkpointer 在测试环境中已初始化
        if not hasattr(app.state, "checkpointer"):
            # 在测试环境中使用 MemorySaver（更快，不需要数据库表）
            test_checkpointer = LangGraphCheckpointer(storage_type="memory")
            await test_checkpointer.setup()
            app.state.checkpointer = test_checkpointer

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac

        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """测试用户 fixture"""
    user = User(
        email=f"test_{uuid.uuid4()}@example.com",  # 使用唯一邮箱避免冲突
        hashed_password="hashed_password",
        name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: User, db_session: AsyncSession) -> dict[str, str]:
    """认证头 fixture"""
    # 延迟导入避免循环依赖
    from domains.identity.application import UserUseCase  # pylint: disable=import-outside-toplevel

    user_uc = UserUseCase(db_session)
    token_pair = await user_uc.create_token(test_user)
    return {"Authorization": f"Bearer {token_pair.access_token}"}


@pytest_asyncio.fixture
async def permission_context(test_user: User):
    """权限上下文 fixture - 为测试用户设置权限上下文"""
    from libs.db.permission_context import (
        PermissionContext,
        clear_permission_context,
        set_permission_context,
    )

    ctx = PermissionContext(user_id=test_user.id, role="user")
    set_permission_context(ctx)
    try:
        yield ctx
    finally:
        clear_permission_context()


@pytest.fixture(scope="session", autouse=True)
def cleanup_litellm():
    """清理 LiteLLM 资源，避免在程序退出时出现日志错误"""
    yield

    # 在测试会话结束时清理 LiteLLM 的日志工作线程
    try:
        import litellm  # pylint: disable=import-outside-toplevel

        # 尝试关闭日志工作线程
        if hasattr(litellm, "logging_worker") and litellm.logging_worker is not None:
            try:
                # 停止日志工作线程
                if hasattr(litellm.logging_worker, "stop"):
                    litellm.logging_worker.stop()
                # 清空日志工作线程引用
                litellm.logging_worker = None
            except Exception:
                pass  # 忽略关闭时的错误

        # 禁用日志回调，避免在退出时触发
        litellm.success_callback = []
        litellm.failure_callback = []
    except Exception:
        pass  # 如果清理失败，忽略（不影响测试结果）


def _suppress_litellm_atexit_errors():
    """
    在 Python 退出时抑制 LiteLLM 的日志错误

    LiteLLM 的 LoggingWorker 在 atexit 时会尝试写日志，
    但此时 stderr 可能已经关闭，导致 ValueError。
    这个函数会替换 verbose_logger 的处理器，使其忽略这些错误。
    """
    try:
        import logging  # pylint: disable=import-outside-toplevel

        from litellm._logging import verbose_logger  # pylint: disable=import-outside-toplevel

        # 移除所有 StreamHandler 避免在关闭时出错
        for handler in verbose_logger.handlers[:]:
            if isinstance(handler, logging.StreamHandler):
                verbose_logger.removeHandler(handler)

        # 添加 NullHandler 作为替代
        verbose_logger.addHandler(logging.NullHandler())
    except Exception:
        pass


# 配置 LiteLLM 的日志处理器，使用安全的处理器避免退出时的错误
# 注意：这只影响测试环境，不影响正常运行
try:
    import logging as _logging  # pylint: disable=ungrouped-imports

    from litellm._logging import verbose_logger as _verbose_logger

    class _SafeStreamHandler(_logging.StreamHandler):
        """安全的 StreamHandler，在流关闭时不抛出异常"""

        def emit(self, record):
            with contextlib.suppress(ValueError, OSError):
                super().emit(record)

        def handleError(self, record):
            """覆盖 handleError，不打印错误信息"""
            pass  # 静默处理错误，避免退出时的错误输出

    # 替换所有 StreamHandler 为安全版本
    for _handler in _verbose_logger.handlers[:]:
        if isinstance(_handler, _logging.StreamHandler):
            # 保留原有的格式和级别
            _safe_handler = _SafeStreamHandler(_handler.stream)
            _safe_handler.setFormatter(_handler.formatter)
            _safe_handler.setLevel(_handler.level)
            _verbose_logger.removeHandler(_handler)
            _verbose_logger.addHandler(_safe_handler)
except Exception:
    pass

# 注册 atexit 处理器作为备用
import atexit  # noqa: E402  # pylint: disable=wrong-import-position,wrong-import-order

atexit.register(_suppress_litellm_atexit_errors)


@pytest.fixture(scope="session", autouse=True)
def cleanup_docker_containers():
    """
    测试会话结束后清理孤儿 Docker 容器
    在多进程测试（pytest-xdist）时，只清理已停止的容器和超时的容器,
    避免影响其他进程正在使用的容器。

    清理策略：
    1. 清理所有已停止的容器（Exited 状态）- 这些是测试正常结束时留下的
    2. 清理运行超过 5 分钟的容器 - 这些可能是泄漏的容器

    为什么不会影响其他进程：
    - 其他进程正在使用的容器运行时间很短（几秒到几分钟），不会被清理
    - 只有已停止的容器和长时间运行的容器（超过 5 分钟）才会被清理
    - 正常测试应该在几分钟内完成，所以不会误删其他进程的容器

    注意：正常测试应该通过 try/finally 或 async with 自己清理容器，
    这个 fixture 只是作为最后的保障，清理可能泄漏的容器。
    """
    yield

    # 在测试会话结束时清理孤儿容器（已停止的或超时的）
    try:
        # pylint: disable=import-outside-toplevel
        from domains.agent.infrastructure.sandbox.executor import (
            SessionDockerExecutor,
        )

        # 清理孤儿容器（已停止的或运行超过 5 分钟的）
        # 使用 nest_asyncio 支持在已有事件循环中运行
        try:
            _ = asyncio.get_running_loop()
            # 如果已有事件循环，使用 nest_asyncio
            nest_asyncio.apply()
            cleaned = asyncio.run(
                SessionDockerExecutor.cleanup_orphaned_containers(max_age_seconds=300)
            )
        except RuntimeError:
            # 没有运行的事件循环，直接运行
            cleaned = asyncio.run(
                SessionDockerExecutor.cleanup_orphaned_containers(max_age_seconds=300)
            )

        if cleaned:
            logger = logging.getLogger(__name__)
            logger.info("Cleaned up %d orphaned test containers: %s", len(cleaned), cleaned)
    except Exception as e:
        # 如果清理失败，记录但不影响测试结果
        logger = logging.getLogger(__name__)
        logger.warning("Failed to cleanup Docker containers: %s", e)
