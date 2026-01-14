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
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Generic,
    Literal,
    Protocol,
    TypedDict,
    TypeVar,
)

from pydantic import BaseModel, ConfigDict, Field

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
    """Agent 事件类型"""

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
    timestamp: datetime = Field(default_factory=datetime.utcnow)


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
    messages: list[dict[str, Any]] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    current_plan: list[str] | None = None
    iteration: int = 0
    total_tokens: int = 0
    pending_tool_call: dict[str, Any] | None = None
    completed: bool = False
    status: Literal["running", "paused", "completed", "error"] = "running"
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentEvent(BaseModel):
    """Agent 事件"""

    type: EventType
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CheckpointMeta(BaseModel):
    """检查点元数据"""

    id: str
    session_id: str
    step: int
    created_at: datetime
    parent_id: str | None = None


class Checkpoint(BaseModel):
    """检查点"""

    id: str
    session_id: str
    step: int
    state: AgentState
    created_at: datetime
    parent_id: str | None = None


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

# JSON 类型
JSONValue = str | int | float | bool | None | dict[str, "JSONValue"] | list["JSONValue"]
JSONSchema = dict[str, Any]
JSONObject = dict[str, Any]

# ID 类型
UserId = str
AgentId = str
SessionId = str
MessageId = str
CheckpointId = str
