"""
LangGraph Store Wrapper - 长期记忆存储

使用 LangGraph Store + 向量数据库的混合架构实现长期记忆管理
- LangGraph Store: 存储元数据和 JSON 文档（支持多种后端：PostgreSQL、InMemory 等）
- VectorStore: 向量搜索（语义相似度）
- LiteLLM: 生成嵌入向量

基于 LangGraph 官方 BaseStore 接口，支持多种 Store 实现
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, Literal
import uuid

from langgraph.store.memory import InMemoryStore
from langgraph.store.postgres import PostgresStore

from app.config import settings
from core.llm.gateway import LLMGateway
from db.vector import VectorStore
from utils.logging import get_logger

logger = get_logger(__name__)


def _create_store_factory(
    store_type: Literal["postgres", "memory"] = "postgres",
):
    """
    创建 LangGraph Store 工厂函数

    基于 LangGraph 官方最佳实践，支持多种 Store 后端：
    - postgres: PostgreSQL 存储（生产环境推荐）
    - memory: 内存存储（开发/测试环境）

    Args:
        store_type: Store 类型

    Returns:
        返回异步上下文管理器的工厂函数

    Raises:
        ImportError: 如果所需的 Store 实现不可用
        ValueError: 如果 store_type 不支持
    """
    if store_type == "postgres":
        # 需要将 postgresql+asyncpg:// 转换为 postgresql://
        db_url = settings.database_url.replace("+asyncpg", "")

        @asynccontextmanager
        async def postgres_store_context():
            # PostgresStore.from_conn_string 返回同步上下文管理器
            # 需要在每次使用时创建新的上下文管理器
            sync_context = PostgresStore.from_conn_string(db_url)

            # 在线程中运行同步上下文管理器，避免阻塞事件循环
            def enter_context():
                return sync_context.__enter__()

            store = await asyncio.to_thread(enter_context)
            try:
                yield store
            finally:
                # 在线程中运行同步上下文管理器的 __exit__
                def exit_context():
                    sync_context.__exit__(None, None, None)

                await asyncio.to_thread(exit_context)

        return postgres_store_context

    elif store_type == "memory":
        # InMemoryStore 不是上下文管理器，需要包装
        @asynccontextmanager
        async def memory_store_context():
            yield InMemoryStore()

        return memory_store_context

    else:
        raise ValueError(f"Unsupported store type: {store_type}")


class LongTermMemoryStore:
    """
    长期记忆存储（混合架构）

    架构设计：
    - LangGraph Store: 存储元数据和 JSON 文档（支持多种后端）
    - VectorStore: 向量搜索（Qdrant/Chroma）
    - LiteLLM: 生成嵌入向量

    职责分离：
    - Store 仅用于元数据，不承担向量搜索
    - 向量数据库专门用于语义搜索，性能更优

    基于 LangGraph 官方 BaseStore 接口，支持：
    - PostgreSQL（生产环境推荐）
    - InMemory（开发/测试环境）
    """

    def __init__(
        self,
        llm_gateway: LLMGateway,
        vector_store: VectorStore,
        store_type: Literal["postgres", "memory"] | None = None,
    ) -> None:
        """
        初始化长期记忆存储

        Args:
            llm_gateway: LiteLLM Gateway 实例（用于生成嵌入向量）
            vector_store: 向量存储实例（Qdrant/Chroma）
            store_type: Store 类型（postgres/memory），默认使用 postgres
        """
        self.llm_gateway = llm_gateway
        self.vector_store = vector_store

        # 从配置或参数获取 store_type（默认使用 postgres）
        store_type = store_type or settings.memory_store_type

        # 使用工厂方法创建 Store（基于 LangGraph 官方最佳实践）
        # _store_context_factory 是一个返回异步上下文管理器的函数
        self._store_context_factory = _create_store_factory(store_type)
        self._store_type = store_type
        logger.info("LongTermMemoryStore initialized with %s backend", store_type)

    async def setup(self) -> None:
        """初始化 Store 和向量集合"""
        # 初始化 store（表结构会在首次使用时自动创建）
        # 注意：这里只是验证连接，实际使用时仍需 async with
        async with self._store_context_factory() as store:
            # 确保表结构已创建
            # PostgresStore 的 setup 是同步方法，需要在线程中运行
            await asyncio.to_thread(store.setup)  # type: ignore[misc]

        # 确保向量集合存在
        await self.vector_store.create_collection(
            name="memories",
            dimension=1536,  # text-embedding-3-small 的维度
        )

        logger.info("LongTermMemoryStore initialized")

    async def search(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
        memory_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        搜索长期记忆（使用向量搜索）

        Args:
            user_id: 用户 ID
            query: 查询文本
            limit: 返回数量
            memory_type: 记忆类型过滤（可选）

        Returns:
            记忆列表，包含 id, content, type, importance, metadata, score
        """
        # 1. 向量搜索（使用 Qdrant/Chroma）
        # 注意：ChromaStore 的 query_filter 需要特殊处理
        vector_results = await self.vector_store.search(
            collection="memories",
            query=query,
            limit=limit * 2,
            query_filter={"user_id": user_id} if user_id else None,
        )

        logger.debug(
            "Vector search returned %d results for user_id=%s, query=%s",
            len(vector_results),
            user_id,
            query,
        )

        # 2. 从 LangGraph Store 获取完整元数据
        memories = []
        namespace = [f"user_{user_id}", "memories"]

        # 使用 async with 确保连接正确管理（连接池会自动复用连接）
        async with self._store_context_factory() as store:
            logger.debug("Processing %d vector results", len(vector_results))
            for result in vector_results:
                memory_id = result["id"]
                logger.debug("Processing memory_id=%s from vector search", memory_id)

                # 构建命名空间
                # 注意：存储时使用的 namespace 是 [user_id, memories, memory_type]
                # 所以搜索时需要尝试所有可能的命名空间组合
                memory_data = None
                possible_namespaces = []

                # 1. 如果 memory_type 参数存在，先尝试带类型的完整 namespace
                if memory_type:
                    possible_namespaces.append([*namespace, memory_type])

                # 2. 从向量结果的 metadata 中获取 memory_type（如果存在）
                # 注意：ChromaStore 返回的 metadata 被展开到顶层，不在 "metadata" 键下
                # 所以应该直接从 result 中获取 memory_type
                result_memory_type = result.get("memory_type")
                logger.debug(
                    "Result keys: %s, memory_type from result: %s",
                    list(result.keys()),
                    result_memory_type,
                )
                if result_memory_type and result_memory_type != memory_type:
                    possible_namespaces.append([*namespace, result_memory_type])

                # 3. 总是尝试不带类型的 namespace（向后兼容）
                possible_namespaces.append(namespace)

                for ns in possible_namespaces:
                    logger.debug("Trying to get memory from namespace %s, key=%s", ns, memory_id)
                    # PostgresStore.get 是同步方法，需要在线程中运行
                    memory_data = await asyncio.to_thread(
                        store.get,
                        namespace=tuple(ns),
                        key=memory_id,
                    )
                    logger.debug(
                        "store.get returned: %s (type: %s)", memory_data, type(memory_data)
                    )
                    if memory_data:
                        logger.debug("Found memory_data from namespace %s", ns)
                        break

                if memory_data:
                    # 处理 memory_data
                    # PostgresStore.get 返回 Item 对象，访问 .value 属性
                    value = memory_data.value

                    # 类型过滤
                    if memory_type and value.get("type") != memory_type:
                        logger.debug(
                            "Memory type mismatch: expected %s, got %s",
                            memory_type,
                            value.get("type"),
                        )
                        continue

                    logger.debug(
                        "Adding memory to results: id=%s, type=%s", memory_id, value.get("type")
                    )
                    memories.append(
                        {
                            "id": memory_id,
                            "content": value.get("content", result.get("text", "")),
                            "type": value.get("type"),
                            "importance": value.get("importance", 0),
                            "metadata": value.get("metadata", {}),
                            "score": result.get("score", 0),
                        }
                    )
                else:
                    logger.warning(
                        "No memory_data found for memory_id=%s in any namespace", memory_id
                    )

        # 3. 按分数和重要性排序
        memories.sort(key=lambda x: (x["score"], x.get("importance", 0)), reverse=True)
        return memories[:limit]

    async def put(
        self,
        user_id: str,
        memory_type: str,
        content: str,
        importance: float = 5.0,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        存储长期记忆（同时存储到 Store 和向量数据库）

        Args:
            user_id: 用户 ID
            memory_type: 记忆类型
            content: 记忆内容
            importance: 重要性 (1-10)
            metadata: 元数据

        Returns:
            记忆 ID
        """
        memory_id = str(uuid.uuid4())
        namespace = [f"user_{user_id}", "memories", memory_type]

        # 1. 存储到 LangGraph Store（元数据）
        value: dict[str, Any] = {
            "content": content,
            "type": memory_type,
            "importance": importance,
            "metadata": metadata or {},
            "created_at": datetime.now(UTC).isoformat(),
        }

        # 使用 async with 确保连接正确管理（连接池会自动复用连接）
        # PostgresStore.put 是同步方法，需要在线程中运行
        async with self._store_context_factory() as store:
            await asyncio.to_thread(
                store.put,
                namespace=tuple(namespace),
                key=memory_id,
                value=value,
            )

        # 2. 存储到向量数据库（用于语义搜索）
        # 注意：VectorStore.upsert 会自动生成嵌入
        # 如果需要统一使用 LiteLLM，可以先生成嵌入：
        # import litellm
        # embedding = await litellm.aembedding(
        #     model=self.llm_gateway.config.embedding_model,
        #     input=content
        # )
        # vector = embedding.data[0]["embedding"]

        await self.vector_store.upsert(
            collection="memories",
            point_id=memory_id,
            text=content,
            metadata={
                "user_id": user_id,
                "memory_type": memory_type,
                "importance": importance,
                **(metadata or {}),
            },
            # vector=vector  # 如果使用 LiteLLM 生成的嵌入，传递这里
        )

        logger.info(
            "Stored memory: %s (type=%s, importance=%.1f)", memory_id, memory_type, importance
        )
        return memory_id

    async def delete(
        self,
        user_id: str,
        memory_id: str,
        memory_type: str,
    ) -> None:
        """
        删除记忆（同时从 Store 和向量数据库删除）

        Args:
            user_id: 用户 ID
            memory_id: 记忆 ID
            memory_type: 记忆类型
        """
        namespace = [f"user_{user_id}", "memories", memory_type]

        # 从 Store 删除
        # 使用 async with 确保连接正确管理（连接池会自动复用连接）
        # PostgresStore.delete 是同步方法，需要在线程中运行
        async with self._store_context_factory() as store:
            await asyncio.to_thread(
                store.delete,
                namespace=tuple(namespace),
                key=memory_id,
            )

        # 从向量数据库删除
        await self.vector_store.delete(
            collection="memories",
            point_ids=[memory_id],
        )

        logger.info("Deleted memory: %s", memory_id)
