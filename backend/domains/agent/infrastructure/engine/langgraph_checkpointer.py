"""
LangGraph Checkpointer Wrapper - 使用 LangGraph 的检查点实现

将 LangGraph 的 AsyncPostgresSaver/MemorySaver 适配为项目现有的 Checkpointer 接口
保持向后兼容

重要：使用 AsyncPostgresSaver（而非同步的 PostgresSaver）以支持异步方法如 aget_tuple。
AsyncPostgresSaver.from_conn_string() 返回一个 async context manager。

设计说明：
使用 AsyncExitStack 来管理 context manager 的生命周期，避免直接调用 __aenter__/__aexit__。
这是 Python 标准库推荐的方式，用于在对象生命周期内管理需要跨方法使用的 context manager。
"""

import asyncio
from contextlib import AsyncExitStack
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from bootstrap.config import settings
from utils.logging import get_logger

logger = get_logger(__name__)


class LangGraphCheckpointer:
    """
    使用 LangGraph 的检查点实现

    支持：
    - PostgreSQL: 生产环境，持久化存储
    - Redis: 高性能场景，快速存储
    - Memory: 开发测试，内存存储

    注意：PostgresSaver 需要作为 context manager 使用，在应用启动时初始化。
    使用 AsyncExitStack 来正确管理 context manager 的生命周期。
    """

    def __init__(
        self,
        storage_type: str = "postgres",
        checkpointer_instance: Any = None,
    ) -> None:
        """
        初始化检查点管理器

        Args:
            storage_type: 存储类型 (postgres/redis/memory)
            checkpointer_instance: 已初始化的 checkpointer 实例（可选，用于共享单例）
        """
        self.storage_type = storage_type
        self._exit_stack: AsyncExitStack | None = None
        self._checkpointer_factory: Any = None

        if checkpointer_instance is not None:
            # 使用提供的实例（通常是全局单例）
            self.checkpointer = checkpointer_instance
            logger.info("Using provided checkpointer instance")
        elif storage_type == "postgres":
            # AsyncPostgresSaver.from_conn_string() 返回 async context manager
            # 保存工厂函数，在 setup() 中通过 AsyncExitStack 管理
            db_url = settings.database_url.replace("+asyncpg", "")
            self._checkpointer_factory = AsyncPostgresSaver.from_conn_string(db_url)
            self.checkpointer = None
            logger.info("AsyncPostgresSaver factory created, will be initialized in setup()")
        elif storage_type == "redis":
            # 注意：RedisSaver 需要特定的 Redis 客户端类型
            # 暂时使用 MemorySaver 作为后备，后续可以完善 Redis 支持
            logger.warning("RedisSaver not fully implemented, using MemorySaver as fallback")
            self.checkpointer = MemorySaver()
        else:
            self.checkpointer = MemorySaver()
            logger.info("Using LangGraph MemorySaver for checkpoints (development mode)")

    async def setup(self) -> None:
        """初始化检查点存储（如果需要）"""
        if self.checkpointer is None and self._checkpointer_factory is not None:
            # 使用 AsyncExitStack 来管理 context manager 的生命周期
            # AsyncExitStack 可以直接使用 enter_async_context()，无需先调用 __aenter__
            # 在 cleanup() 中通过 aclose() 统一关闭所有注册的 context managers
            try:
                self._exit_stack = AsyncExitStack()

                # 通过 exit_stack 进入 context manager，获取实际实例
                self.checkpointer = await self._exit_stack.enter_async_context(
                    self._checkpointer_factory
                )

                # 调用 setup 初始化表结构
                await self._call_setup_if_available(self.checkpointer)
                logger.info("AsyncPostgresSaver initialized and setup completed")
            except Exception as e:
                # 如果初始化失败，清理 exit_stack
                if self._exit_stack is not None:
                    await self._exit_stack.aclose()
                    self._exit_stack = None
                logger.error("Failed to initialize AsyncPostgresSaver: %s", e, exc_info=True)
                raise
        elif self.checkpointer is not None and hasattr(self.checkpointer, "setup"):
            # 如果已经有实例，直接调用 setup
            try:
                await self._call_setup_if_available(self.checkpointer)
                logger.info("Checkpointer setup completed")
            except Exception as e:
                logger.warning("Checkpointer setup failed (may already be initialized): %s", e)

    async def _call_setup_if_available(self, checkpointer: Any) -> None:
        """安全调用 setup 方法，处理同步和异步两种情况"""
        if not hasattr(checkpointer, "setup"):
            return

        setup_result = checkpointer.setup()
        # 检查是否返回了协程对象
        if asyncio.iscoroutine(setup_result):
            await setup_result
        # 如果不是协程（同步方法返回 None），则不需要 await

    async def cleanup(self) -> None:
        """清理资源（关闭 context manager）"""
        if self._exit_stack is not None:
            try:
                await self._exit_stack.aclose()
                logger.info("Checkpointer context manager closed via AsyncExitStack")
            except Exception as e:
                logger.warning("Error closing checkpointer context manager: %s", e)
            finally:
                self._exit_stack = None

    def get_config(self, thread_id: str) -> dict[str, Any]:
        """
        获取 LangGraph 配置字典

        Args:
            thread_id: 线程 ID（会话 ID）

        Returns:
            LangGraph 配置字典
        """
        return {
            "configurable": {
                "thread_id": thread_id,
            }
        }

    def get_checkpointer(self):
        """
        获取原始的 LangGraph Checkpointer 实例

        用于直接传递给 LangGraph 的图编译

        Returns:
            LangGraph Checkpointer 实例
        """
        if self.checkpointer is None:
            logger.warning(
                "get_checkpointer() called but checkpointer is None! "
                "Did you forget to call setup()? storage_type=%s",
                self.storage_type,
            )
        return self.checkpointer


# 向后兼容：保持原有 Checkpoint 类型定义
__all__ = ["LangGraphCheckpointer"]
