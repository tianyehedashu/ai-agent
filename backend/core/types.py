"""
Core Types - Agent 架构核心类型定义

提供强类型支持，包括:
- 枚举类型
- Pydantic 模型 (运行时验证)
- Protocol 定义 (结构化类型)
- TypedDict (字典类型约束)
- 泛型类型
- 类型别名
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
import logging
from typing import (
    Any,
    Generic,
    Literal,
    Protocol,
    TypedDict,
    TypeVar,
)

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from utils.serialization import SerializableDict, Serializer

logger = logging.getLogger(__name__)

# ============================================================================
# 基础枚举类型
# ============================================================================


class AgentMode(str, Enum):
    """Agent 运行模式"""

    EXECUTE = "execute"  # 完整执行权限
    ANALYZE = "analyze"  # 只读分析模式


class ToolCategory(str, Enum):
    """工具分类"""

    FILE = "file"
    CODE = "code"
    SEARCH = "search"
    DATABASE = "database"
    NETWORK = "network"
    SYSTEM = "system"
    EXTERNAL = "external"  # 外部工具 (MCP等)


class MessageRole(str, Enum):
    """消息角色"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class EventType(str, Enum):
    """Agent 事件类型

    统一的事件类型定义，用于 Agent 引擎和 API 层。
    使用 StrEnum 继承，可以直接用于 JSON 序列化。
    """

    SESSION_CREATED = "session_created"
    SESSION_RECREATED = "session_recreated"
    THINKING = "thinking"
    TEXT = "text"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    INTERRUPT = "interrupt"
    DONE = "done"
    ERROR = "error"
    TERMINATED = "terminated"


class TerminationReason(str, Enum):
    """终止原因"""

    MAX_ITERATIONS = "max_iterations_exceeded"
    TOKEN_BUDGET = "token_budget_exceeded"
    TIMEOUT = "timeout"
    USER_CANCELLED = "user_cancelled"
    TASK_COMPLETE = "task_complete"
    ERROR = "error"


# ============================================================================
# Pydantic 模型 (运行时验证)
# ============================================================================


class ToolCall(BaseModel):
    """工具调用"""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    """工具执行结果"""

    model_config = ConfigDict(frozen=True)

    tool_call_id: str
    success: bool
    output: str
    error: str | None = None
    duration_ms: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    """消息模型"""

    model_config = ConfigDict(frozen=True)

    role: MessageRole
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentConfig(BaseModel):
    """Agent 配置"""

    model_config = ConfigDict(strict=True)

    name: str = Field(min_length=1, max_length=100)
    mode: AgentMode = AgentMode.EXECUTE
    model: str = "claude-3-5-sonnet-20241022"
    max_iterations: int = Field(default=20, ge=1, le=100)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=1, le=128000)
    tools: list[str] = Field(default_factory=list)
    system_prompt: str | None = None

    # 检查点配置
    checkpoint_enabled: bool = True
    checkpoint_interval: int = Field(default=5, ge=1)

    # HITL 配置
    hitl_enabled: bool = True
    hitl_operations: list[str] = Field(
        default_factory=lambda: ["run_shell", "write_file", "delete_file"]
    )


class TerminationCondition(BaseModel):
    """终止条件配置"""

    max_iterations: int = Field(default=20, ge=1, le=100)
    max_tokens: int = Field(default=100000, ge=1000)
    timeout_seconds: int = Field(default=600, ge=10)
    stop_texts: list[str] = Field(default_factory=list)


class InterruptConfig(BaseModel):
    """Human-in-the-Loop 中断配置"""

    interrupt_before: list[str] = Field(default_factory=list)
    interrupt_after: list[str] = Field(default_factory=list)
    auto_approve_patterns: list[str] = Field(default_factory=list)


class AgentState(BaseModel):
    """Agent 状态 (用于检查点)"""

    session_id: str
    messages: list[Message] = Field(default_factory=list)
    # 使用 SerializableDict 类型，提供运行时验证和序列化保证
    # PlainValidator 会在验证时自动调用序列化工具，确保数据可序列化
    context: SerializableDict = Field(default_factory=dict)
    current_plan: list[str] | None = None
    iteration: int = 0
    total_tokens: int = 0
    pending_tool_call: SerializableDict | None = None
    completed: bool = False
    status: Literal["running", "paused", "completed", "error"] = "running"
    metadata: SerializableDict = Field(default_factory=dict)


# ============================================================================
# 事件数据模型 - 类型安全的数据结构
# ============================================================================


class FinalMessage(BaseModel):
    """最终消息结构

    支持普通模型和推理模型：
    - content: 最终回复内容（所有模型）
    - reasoning_content: 推理过程（推理模型，如 DeepSeek Reasoner）
    """

    model_config = ConfigDict(frozen=True)

    content: str
    reasoning_content: str | None = None


class ThinkingEventData(BaseModel):
    """思考事件数据"""

    model_config = ConfigDict(frozen=True)

    status: str  # "processing", "reasoning", "analyzing"
    iteration: int = 1
    content: str | None = None  # 推理模型的思考内容


class TextEventData(BaseModel):
    """文本事件数据"""

    model_config = ConfigDict(frozen=True)

    content: str


class DoneEventData(BaseModel):
    """完成事件数据"""

    model_config = ConfigDict(frozen=True)

    iterations: int = 1
    tool_iterations: int = 0
    total_tokens: int = 0
    final_message: FinalMessage


class ErrorEventData(BaseModel):
    """错误事件数据"""

    model_config = ConfigDict(frozen=True)

    error: str
    session_id: str | None = None


class ToolCallEventData(BaseModel):
    """工具调用事件数据"""

    model_config = ConfigDict(frozen=True)

    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResultEventData(BaseModel):
    """工具结果事件数据"""

    model_config = ConfigDict(frozen=True)

    tool_call_id: str
    tool_name: str
    success: bool
    output: str
    error: str | None = None
    duration_ms: int | None = None


class SessionEventData(BaseModel):
    """会话事件数据"""

    model_config = ConfigDict(frozen=True)

    session_id: str


# ============================================================================
# AgentEvent - 统一事件模型
# ============================================================================


class AgentEvent(BaseModel):
    """Agent 事件

    统一的事件模型，用于 Agent 引擎和 API 层。
    支持类型安全的工厂方法和数据访问。

    Usage:
        # 方式 1: 传统字典方式（向后兼容）
        event = AgentEvent(type=EventType.DONE, data={"final_message": {"content": "Hi"}})

        # 方式 2: 类型安全方式（推荐）
        event = AgentEvent.done(content="Hi", reasoning_content="思考过程")
    """

    model_config = ConfigDict()

    type: EventType
    data: SerializableDict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="before")
    @classmethod
    def validate_all_data(cls, data: Any) -> Any:
        """在模型验证之前，深度序列化所有数据"""
        if isinstance(data, dict) and "data" in data:
            event_data = data["data"]
            if isinstance(event_data, BaseModel):
                event_data = event_data.model_dump()
            data["data"] = (
                Serializer.serialize_dict(event_data)
                if isinstance(event_data, dict)
                else Serializer.serialize(event_data)
            )
        return data

    @model_serializer(mode="wrap")
    def serialize_model(self, serializer: Any, info: Any) -> dict[str, Any]:
        """自定义序列化，确保所有嵌套对象都被正确序列化"""
        result = serializer(self)
        if isinstance(result, dict) and "data" in result:
            result["data"] = Serializer.serialize_dict(result["data"])
        return result

    # =========================================================================
    # 类型安全的工厂方法
    # =========================================================================

    @classmethod
    def session_created(cls, session_id: str) -> AgentEvent:
        """创建会话创建事件"""
        return cls(
            type=EventType.SESSION_CREATED,
            data=SessionEventData(session_id=session_id).model_dump(),
        )

    @classmethod
    def thinking(
        cls,
        status: str = "processing",
        iteration: int = 1,
        content: str | None = None,
    ) -> AgentEvent:
        """创建思考事件"""
        return cls(
            type=EventType.THINKING,
            data=ThinkingEventData(
                status=status, iteration=iteration, content=content
            ).model_dump(),
        )

    @classmethod
    def text(cls, content: str) -> AgentEvent:
        """创建文本事件"""
        return cls(
            type=EventType.TEXT,
            data=TextEventData(content=content).model_dump(),
        )

    @classmethod
    def done(
        cls,
        content: str,
        reasoning_content: str | None = None,
        iterations: int = 1,
        tool_iterations: int = 0,
        total_tokens: int = 0,
    ) -> AgentEvent:
        """创建完成事件"""
        return cls(
            type=EventType.DONE,
            data=DoneEventData(
                iterations=iterations,
                tool_iterations=tool_iterations,
                total_tokens=total_tokens,
                final_message=FinalMessage(content=content, reasoning_content=reasoning_content),
            ).model_dump(),
        )

    @classmethod
    def error(cls, error: str, session_id: str | None = None) -> AgentEvent:
        """创建错误事件"""
        return cls(
            type=EventType.ERROR,
            data=ErrorEventData(error=error, session_id=session_id).model_dump(),
        )

    @classmethod
    def tool_call(
        cls,
        tool_call_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> AgentEvent:
        """创建工具调用事件"""
        return cls(
            type=EventType.TOOL_CALL,
            data=ToolCallEventData(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                arguments=arguments or {},
            ).model_dump(),
        )

    @classmethod
    def tool_result(
        cls,
        tool_call_id: str,
        tool_name: str,
        success: bool,
        output: str,
        error: str | None = None,
        duration_ms: int | None = None,
    ) -> AgentEvent:
        """创建工具结果事件"""
        return cls(
            type=EventType.TOOL_RESULT,
            data=ToolResultEventData(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                success=success,
                output=output,
                error=error,
                duration_ms=duration_ms,
            ).model_dump(),
        )

    # =========================================================================
    # 类型安全的数据访问方法
    # =========================================================================

    def get_final_message(self) -> FinalMessage | None:
        """获取最终消息（类型安全）"""
        if self.type != EventType.DONE:
            return None
        final_msg = self.data.get("final_message")
        if not final_msg:
            return None
        return FinalMessage(
            content=final_msg.get("content", ""),
            reasoning_content=final_msg.get("reasoning_content"),
        )

    def get_content(self) -> str:
        """获取事件内容（通用方法）"""
        if self.type in (EventType.TEXT, EventType.THINKING):
            return self.data.get("content", "")
        if self.type == EventType.DONE:
            final_msg = self.get_final_message()
            if final_msg:
                return final_msg.content or final_msg.reasoning_content or ""
        return ""


class CheckpointMeta(BaseModel):
    """检查点元数据"""

    id: str
    session_id: str
    step: int
    created_at: datetime
    parent_id: str | None = None


class Checkpoint(BaseModel):
    """检查点"""

    model_config = ConfigDict(
        # 移除 ser_json_infra=True，避免 Pydantic 内部序列化检查导致警告
        # ser_json_infra=True,  # 注释掉，看看是否能解决问题
    )

    id: str
    session_id: str
    step: int
    state: AgentState
    created_at: datetime
    parent_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_state(cls, data: Any) -> Any:
        """在模型验证之前，确保 state 中的数据是可序列化的"""
        if isinstance(data, dict) and "state" in data:
            state_data = data["state"]
            if isinstance(state_data, dict):
                # 确保 state 中的 context 和 metadata 是可序列化的
                if "context" in state_data:
                    state_data["context"] = Serializer.serialize_dict(state_data["context"])
                if "metadata" in state_data:
                    state_data["metadata"] = Serializer.serialize_dict(state_data["metadata"])
        return data


# ============================================================================
# Protocol 定义 (结构化类型)
# ============================================================================


class ToolProtocol(Protocol):
    """工具协议 - 所有工具必须实现"""

    @property
    def name(self) -> str:
        """工具名称"""
        ...

    @property
    def description(self) -> str:
        """工具描述"""
        ...

    @property
    def parameters(self) -> dict[str, Any]:
        """JSON Schema 参数定义"""
        ...

    @property
    def category(self) -> ToolCategory:
        """工具分类"""
        ...

    @property
    def requires_confirmation(self) -> bool:
        """是否需要确认"""
        ...

    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行工具"""
        ...


class CheckpointerProtocol(Protocol):
    """检查点协议"""

    async def save(self, session_id: str, step: int, state: AgentState) -> str:
        """保存检查点，返回 checkpoint_id"""
        ...

    async def load(self, checkpoint_id: str) -> AgentState:
        """加载检查点"""
        ...

    async def get_latest(self, session_id: str) -> Checkpoint | None:
        """获取最新检查点"""
        ...

    async def list_history(self, session_id: str, limit: int = 50) -> list[Checkpoint]:
        """列出会话的所有检查点"""
        ...


class LLMProviderProtocol(Protocol):
    """LLM 提供商协议"""

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
    ) -> Any:
        """聊天补全"""
        ...

    async def embed(self, text: str) -> list[float]:
        """文本嵌入"""
        ...


class MemoryRetrieverProtocol(Protocol):
    """记忆检索协议"""

    async def retrieve(
        self,
        query: str,
        session_id: str,
        max_tokens: int = 2000,
        top_k: int = 10,
    ) -> list[Any]:
        """检索相关记忆"""
        ...


# ============================================================================
# TypedDict (字典类型约束)
# ============================================================================


class NodeDefinition(TypedDict):
    """节点定义 (用于 Code-First 解析)"""

    id: str
    name: str
    func_name: str
    position: tuple[int, int]


class EdgeDefinition(TypedDict):
    """边定义"""

    source: str
    target: str
    condition: str | None


class WorkflowDefinition(TypedDict):
    """工作流定义"""

    nodes: list[NodeDefinition]
    edges: list[EdgeDefinition]
    entry_point: str


class ToolDefinitionDict(TypedDict):
    """工具定义字典"""

    name: str
    description: str
    parameters: dict[str, Any]
    category: str
    requires_confirmation: bool


# ============================================================================
# 泛型类型
# ============================================================================

T = TypeVar("T")
StateT = TypeVar("StateT", bound=BaseModel)


@dataclass
class Result(Generic[T]):
    """
    结果类型 (类似 Rust Result)

    用法:
        result = Result.ok(value)
        result = Result.err("error message")

        if result.is_ok:
            value = result.unwrap()
        else:
            error = result.error
    """

    _value: T | None = None
    _error: str | None = None

    @property
    def is_ok(self) -> bool:
        return self._error is None

    @property
    def is_err(self) -> bool:
        return self._error is not None

    @property
    def error(self) -> str | None:
        return self._error

    def unwrap(self) -> T:
        if self._error:
            raise ValueError(self._error)
        if self._value is None:
            raise ValueError("Result value is None")
        return self._value

    def unwrap_or(self, default: T) -> T:
        return self._value if self.is_ok and self._value is not None else default

    def map(self, func: Callable[[T], T]) -> Result[T]:
        if self.is_ok and self._value is not None:
            return Result.ok(func(self._value))
        return Result.err(self._error or "Unknown error")

    @classmethod
    def ok(cls, value: T) -> Result[T]:
        return cls(_value=value)

    @classmethod
    def err(cls, error: str) -> Result[T]:
        return cls(_error=error)


# ============================================================================
# 类型别名
# ============================================================================

# 函数类型
ToolExecutor = Callable[..., Awaitable[ToolResult]]
NodeFunction = Callable[[AgentState], Awaitable[AgentState]]
ConditionFunction = Callable[[AgentState], str]
EventGenerator = "AsyncGenerator[AgentEvent, None]"

# JSON 类型（已移至 utils.serialization，保留别名以保持兼容性）
JSONSchema = dict[str, Any]

# ID 类型
UserId = str
AgentId = str
SessionId = str
MessageId = str
CheckpointId = str
