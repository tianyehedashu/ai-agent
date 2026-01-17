"""
Vector Store - 向量数据库封装

支持:
- Qdrant (生产环境)
- Chroma (开发环境)

Embedding 使用统一的 EmbeddingService，支持：
- API 模式: OpenAI, 火山引擎, 阿里云等（通过 LiteLLM）
- 本地模式: FastEmbed (BAAI/bge 系列，CPU 友好，无需 GPU)
"""

from abc import ABC, abstractmethod
from typing import Any

import chromadb
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointIdsList,
    PointStruct,
    VectorParams,
)

from app.config import settings
from core.llm.embeddings import EmbeddingService
from services.embedding import get_embedding_service_from_settings
from utils.logging import get_logger

logger = get_logger(__name__)


class VectorStore(ABC):
    """向量存储抽象基类"""

    @abstractmethod
    async def create_collection(
        self,
        name: str,
        dimension: int = 1536,
    ) -> None:
        """创建集合"""
        raise NotImplementedError

    @abstractmethod
    async def delete_collection(self, name: str) -> None:
        """删除集合"""
        raise NotImplementedError

    @abstractmethod
    async def upsert(
        self,
        collection: str,
        point_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
        vector: list[float] | None = None,
    ) -> None:
        """插入或更新向量"""
        raise NotImplementedError

    @abstractmethod
    async def search(
        self,
        collection: str,
        query: str,
        limit: int = 10,
        query_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """搜索相似向量"""
        raise NotImplementedError

    @abstractmethod
    async def delete(
        self,
        collection: str,
        point_ids: list[str],
    ) -> None:
        """删除向量"""
        raise NotImplementedError


class QdrantStore(VectorStore):
    """Qdrant 向量存储"""

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.url = url or settings.qdrant_url
        self.api_key = api_key or settings.qdrant_api_key
        self._client = None
        self._embedding_service: EmbeddingService | None = None

    async def _get_client(self):
        """获取 Qdrant 客户端"""
        if self._client is None:
            self._client = AsyncQdrantClient(
                url=self.url,
                api_key=self.api_key,
            )
        return self._client

    async def create_collection(
        self,
        name: str,
        dimension: int = 1536,
    ) -> None:
        """创建集合"""
        client = await self._get_client()

        # 检查集合是否存在
        collections = await client.get_collections()
        if name in [c.name for c in collections.collections]:
            return

        await client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(
                size=dimension,
                distance=Distance.COSINE,
            ),
        )
        logger.info("Created collection: %s", name)

    async def delete_collection(self, name: str) -> None:
        """删除集合"""
        client = await self._get_client()
        await client.delete_collection(collection_name=name)
        logger.info("Deleted collection: %s", name)

    async def upsert(
        self,
        collection: str,
        point_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
        vector: list[float] | None = None,
    ) -> None:
        """插入或更新向量"""
        client = await self._get_client()

        # 生成向量
        if vector is None:
            vector = await self._get_embedding(text)

        # 准备 payload
        payload = {"text": text, **(metadata or {})}

        await client.upsert(
            collection_name=collection,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            ],
        )

    async def search(
        self,
        collection: str,
        query: str,
        limit: int = 10,
        query_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """搜索相似向量"""
        client = await self._get_client()

        # 生成查询向量
        query_vector = await self._get_embedding(query)

        # 构建过滤条件
        qdrant_filter = None
        if query_filter:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v)) for k, v in query_filter.items()
            ]
            qdrant_filter = Filter(must=conditions)

        # 搜索
        results = await client.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=limit,
            query_filter=qdrant_filter,
        )

        return [
            {
                "id": str(r.id),
                "score": r.score,
                "text": r.payload.get("text", ""),
                **{k: v for k, v in r.payload.items() if k != "text"},
            }
            for r in results
        ]

    async def delete(
        self,
        collection: str,
        point_ids: list[str],
    ) -> None:
        """删除向量"""
        client = await self._get_client()
        await client.delete(
            collection_name=collection,
            points_selector=PointIdsList(points=point_ids),
        )

    def _get_embedding_service(self) -> EmbeddingService:
        """
        懒加载 EmbeddingService

        支持 API 和本地模型两种模式：
        - API 模式: OpenAI, 火山引擎等（通过 LiteLLM）
        - 本地模式: FastEmbed (BAAI/bge 系列，CPU 友好)
        """
        if self._embedding_service is None:
            self._embedding_service = get_embedding_service_from_settings()
        return self._embedding_service

    async def _get_embedding(self, text: str) -> list[float]:
        """
        获取文本嵌入

        使用统一的 EmbeddingService，支持 API 和本地模型
        """
        service = self._get_embedding_service()
        return await service.embed(text)


class ChromaStore(VectorStore):
    """Chroma 向量存储 (开发环境)"""

    def __init__(self, persist_directory: str | None = None) -> None:
        self.persist_directory = persist_directory or "./chroma_data"
        self._client = None
        self._collections: dict[str, Any] = {}

    def _get_client(self):
        """获取 Chroma 客户端"""
        if self._client is None:
            self._client = chromadb.PersistentClient(path=self.persist_directory)
        return self._client

    async def create_collection(
        self,
        name: str,
        dimension: int = 1536,
    ) -> None:
        """创建集合"""
        client = self._get_client()
        self._collections[name] = client.get_or_create_collection(name=name)
        logger.info("Created collection: %s", name)

    async def delete_collection(self, name: str) -> None:
        """删除集合"""
        client = self._get_client()
        client.delete_collection(name=name)
        if name in self._collections:
            del self._collections[name]
        logger.info("Deleted collection: %s", name)

    async def upsert(
        self,
        collection: str,
        point_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
        vector: list[float] | None = None,
    ) -> None:
        """插入或更新向量"""
        if collection not in self._collections:
            await self.create_collection(collection)

        coll = self._collections[collection]

        # Chroma 会自动生成嵌入
        coll.upsert(
            ids=[point_id],
            documents=[text],
            metadatas=[metadata] if metadata else None,
            embeddings=[vector] if vector else None,
        )

    async def search(
        self,
        collection: str,
        query: str,
        limit: int = 10,
        query_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """搜索相似向量"""
        if collection not in self._collections:
            await self.create_collection(collection)

        coll = self._collections[collection]

        results = coll.query(
            query_texts=[query],
            n_results=limit,
            where=query_filter,
        )

        items = []
        if results["ids"] and results["ids"][0]:
            for i, point_id in enumerate(results["ids"][0]):
                items.append(
                    {
                        "id": point_id,
                        "score": 1 - results["distances"][0][i] if results["distances"] else 0,
                        "text": results["documents"][0][i] if results["documents"] else "",
                        **(results["metadatas"][0][i] if results["metadatas"] else {}),
                    }
                )

        return items

    async def delete(
        self,
        collection: str,
        point_ids: list[str],
    ) -> None:
        """删除向量"""
        if collection not in self._collections:
            return

        coll = self._collections[collection]
        coll.delete(ids=point_ids)


def get_vector_store() -> VectorStore:
    """获取向量存储实例"""
    if settings.debug:
        return ChromaStore()
    return QdrantStore()


# 别名，用于兼容性
get_vector_client = get_vector_store
