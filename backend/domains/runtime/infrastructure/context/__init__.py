"""
Context Manager - 上下文管理器

负责组装和管理 Agent 的上下文

智能压缩策略（基于最新研究 SimpleMem, PAACE 等）：
1. 关键消息检测 - 识别任务定义、约束、决策点
2. 计划感知压缩 - 根据任务计划结构智能选择
3. 重要性评分 - 多维度评分（位置、角色、内容）
4. 摘要压缩 - 将低重要性的早期对话压缩为摘要
5. 固定记忆 - 关键消息永不删除
"""

from domains.runtime.infrastructure.context.key_detector import (
    DetectionResult,
    KeyMessageDetector,
    KeyMessageDetectorConfig,
    KeyMessageType,
    get_key_detector,
)
from domains.runtime.infrastructure.context.manager import ContextManager
from domains.runtime.infrastructure.context.plan_tracker import (
    PlanStep,
    PlanTracker,
    TaskPlan,
    TaskStatus,
    TaskType,
)
from domains.runtime.infrastructure.context.smart_compressor import (
    CompressionConfig,
    CompressionResult,
    MessageImportance,
    ScoredMessage,
    SmartContextCompressor,
)
from domains.runtime.infrastructure.context.smart_manager import (
    ContextBuildResult,
    SmartContextConfig,
    SmartContextManager,
    get_smart_context_manager,
)

__all__ = [
    "CompressionConfig",
    "CompressionResult",
    "ContextBuildResult",
    "ContextManager",
    "DetectionResult",
    "KeyMessageDetector",
    "KeyMessageDetectorConfig",
    "KeyMessageType",
    "MessageImportance",
    "PlanStep",
    "PlanTracker",
    "ScoredMessage",
    "SmartContextCompressor",
    "SmartContextConfig",
    "SmartContextManager",
    "TaskPlan",
    "TaskStatus",
    "TaskType",
    "get_key_detector",
    "get_smart_context_manager",
]
