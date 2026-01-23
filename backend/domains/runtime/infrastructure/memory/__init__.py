"""Memory Module - 记忆模块

提供多层次的记忆管理能力：
- LongTermMemoryStore: 长期记忆存储（向量检索）
- MemoryExtractor: 记忆提取器
- MemorySummarizer: 记忆摘要器（Token 优化）
- TieredMemoryManager: 分层记忆管理器
- SimpleMemClient: SimpleMem MCP 客户端（30x Token 压缩）
"""

from domains.runtime.infrastructure.memory.extractor import MemoryExtractor
from domains.runtime.infrastructure.memory.langgraph_store import LongTermMemoryStore
from domains.runtime.infrastructure.memory.simplemem_client import (
    SimpleMemAdapter,
    SimpleMemConfig,
    get_simplemem_adapter,
    reset_simplemem_adapter,
)
from domains.runtime.infrastructure.memory.summarizer import MemorySummarizer, SummarizationConfig, SummarizationResult
from domains.runtime.infrastructure.memory.tiered_memory import (
    MemoryItem,
    MemoryTier,
    MemoryType,
    RecallResult,
    TieredMemoryConfig,
    TieredMemoryManager,
)

__all__ = [
    "LongTermMemoryStore",
    "MemoryExtractor",
    "MemoryItem",
    "MemorySummarizer",
    "MemoryTier",
    "MemoryType",
    "RecallResult",
    "SimpleMemAdapter",
    "SimpleMemConfig",
    "SummarizationConfig",
    "SummarizationResult",
    "TieredMemoryConfig",
    "TieredMemoryManager",
    "get_simplemem_adapter",
    "reset_simplemem_adapter",
]
