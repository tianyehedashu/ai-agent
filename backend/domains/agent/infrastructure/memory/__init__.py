"""Memory Module - 记忆模块

提供多层次的记忆管理能力：
- LongTermMemoryStore: 长期记忆存储（向量检索）
- MemoryExtractor: 记忆提取器
- MemorySummarizer: 记忆摘要器（Token 优化）
- TieredMemoryManager: 分层记忆管理器
- SimpleMemClient: SimpleMem MCP 客户端（30x Token 压缩）
- CheckpointCache: 检查点缓存（短期记忆存储）
"""

from domains.agent.infrastructure.memory.checkpoint_cache import CheckpointCache
from domains.agent.infrastructure.memory.extractor import MemoryExtractor
from domains.agent.infrastructure.memory.langgraph_store import LongTermMemoryStore
from domains.agent.infrastructure.memory.simplemem_client import (
    SimpleMemAdapter,
    SimpleMemConfig,
    get_simplemem_adapter,
    reset_simplemem_adapter,
)
from domains.agent.infrastructure.memory.summarizer import (
    MemorySummarizer,
    SummarizationConfig,
    SummarizationResult,
)
from domains.agent.infrastructure.memory.tiered_memory import (
    MemoryItem,
    MemoryTier,
    MemoryType,
    RecallResult,
    TieredMemoryConfig,
    TieredMemoryManager,
)

__all__ = [
    "CheckpointCache",
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
