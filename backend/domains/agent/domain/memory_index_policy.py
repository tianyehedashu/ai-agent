"""记忆向量索引策略（纯函数，无 IO）。"""

from __future__ import annotations

from typing import Any, Literal

MemoryIndexPurpose = Literal["session", "knowledge"]

SESSION_MEMORY_COLLECTION = "memories"


def memory_collection_name(*, purpose: MemoryIndexPurpose = "session") -> str:
    """向量 collection 名称。"""
    if purpose == "session":
        return SESSION_MEMORY_COLLECTION
    return f"kb_{purpose}"


def langgraph_namespace(session_id: str, memory_type: str) -> tuple[str, ...]:
    """LangGraph Store 写入命名空间。"""
    return (f"session_{session_id}", "memories", memory_type)


def langgraph_namespace_prefix(session_id: str) -> tuple[str, ...]:
    """搜索时回退用的前缀 namespace（兼容旧数据）。"""
    return (f"session_{session_id}", "memories")


def langgraph_namespace_candidates(
    session_id: str,
    *,
    memory_type: str | None,
    result_memory_type: str | None,
) -> list[tuple[str, ...]]:
    """按优先级尝试的 LangGraph namespace 列表。"""
    prefix = langgraph_namespace_prefix(session_id)
    candidates: list[tuple[str, ...]] = []
    if memory_type:
        candidates.append(langgraph_namespace(session_id, memory_type))
    if result_memory_type and result_memory_type != memory_type:
        candidates.append(langgraph_namespace(session_id, result_memory_type))
    if prefix not in candidates:
        candidates.append(prefix)
    return candidates


def vector_filter_for_session(session_id: str) -> dict[str, Any]:
    """向量库检索过滤条件（session 隔离）。"""
    return {"session_id": session_id}


def vector_payload_for_memory(
    *,
    session_id: str,
    memory_type: str,
    content: str,
    importance: float,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """写入向量库的 payload（含可检索文本）。"""
    return {
        "text": content,
        "session_id": session_id,
        "memory_type": memory_type,
        "importance": importance,
        **(metadata or {}),
    }
