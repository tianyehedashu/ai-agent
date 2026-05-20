"""向量库后端选择策略（纯函数）。"""

from __future__ import annotations

from typing import Literal

VectorBackendType = Literal["qdrant", "chroma"]


def effective_vector_db_type(
    configured: VectorBackendType,
    *,
    pytest_chroma_ephemeral: bool,
) -> VectorBackendType:
    """pytest 内存 Chroma 优先；否则使用配置的 ``vector_db_type``。"""
    if pytest_chroma_ephemeral:
        return "chroma"
    return configured
