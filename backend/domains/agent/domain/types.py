"""
Runtime Domain Types - 运行时域类型定义

包含 Agent 运行时的核心类型：
- MessageRole, Message: 消息模型
- EventType, AgentEvent, *EventData: 事件系统
- AgentMode, AgentConfig, AgentState: Agent 配置和状态
- ToolCategory, ToolCall, ToolResult, ToolProtocol: 工具系统
- Checkpoint*, CheckpointerProtocol: 检查点系统
- TerminationReason, TerminationCondition, InterruptConfig: 终止条件
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from enum import Enum
from typing import Any, ClassVar, Literal, Protocol, TypedDict, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from utils.serialization import SerializableDict, Serializer

# ============================================================================
# 消息模型
# ============================================================================


class MessageRole(str, Enum):
    """消息角色"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(BaseModel):
    """消息模型"""

    model_config = ConfigDict(frozen=True)

    role: MessageRole
    content: str | None = None
    tool_calls: list[Any] | None = None
    tool_call_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ============================================================================
# 事件类型
# ============================================================================


class EventType(str, Enum):
    """Agent 事件类型"""

    SESSION_CREATED = "session_created"
    SESSION_RECREATED = "session_recreated"
    TITLE_UPDATED = "title_updated"
    THINKING = "thinking"
    TEXT = "text"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    INTERRUPT = "interrupt"
    DONE = "done"
    ERROR = "error"
    TERMINATED = "terminated"


# ============================================================================
# 事件数据模型
# ============================================================================


class FinalMessage(BaseModel):
    """最终消息结构"""

    model_config = ConfigDict(frozen=True)

    content: str
    reasoning_content: str | None = None


class ThinkingEventData(BaseModel):
    """思考事件数据"""

    model_config = ConfigDict(frozen=True)

    status: str
    iteration: int = 1
    content: str | None = None


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


class TitleUpdatedEventData(BaseModel):
    """标题更新事件数据"""

    model_config = ConfigDict(frozen=True)

    session_id: str
    title: str


# ============================================================================
# AgentEvent - 统一事件模型
# ============================================================================


class AgentEvent(BaseModel):
    """Agent 事件"""

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
        """自定义序列化"""
        result = serializer(self)
        if isinstance(result, dict) and "data" in result:
            result["data"] = Serializer.serialize_dict(result["data"])
        return result

    # 工厂方法
    @classmethod
    def session_created(cls, session_id: str) -> AgentEvent:
        return cls(
            type=EventType.SESSION_CREATED,
            data=SessionEventData(session_id=session_id).model_dump(),
        )

    @classmethod
    def title_updated(cls, session_id: str, title: str) -> AgentEvent:
        return cls(
            type=EventType.TITLE_UPDATED,
            data=TitleUpdatedEventData(session_id=session_id, title=title).model_dump(),
        )

    @classmethod
    def thinking(
        cls, status: str = "processing", iteration: int = 1, content: str | None = None
    ) -> AgentEvent:
        return cls(
            type=EventType.THINKING,
            data=ThinkingEventData(
                status=status, iteration=iteration, content=content
            ).model_dump(),
        )

    @classmethod
    def text(cls, content: str) -> AgentEvent:
        return cls(type=EventType.TEXT, data=TextEventData(content=content).model_dump())

    @classmethod
    def done(
        cls,
        content: str,
        reasoning_content: str | None = None,
        iterations: int = 1,
        tool_iterations: int = 0,
        total_tokens: int = 0,
    ) -> AgentEvent:
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
        return cls(
            type=EventType.ERROR,
            data=ErrorEventData(error=error, session_id=session_id).model_dump(),
        )

    @classmethod
    def tool_call(
        cls, tool_call_id: str, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> AgentEvent:
        return cls(
            type=EventType.TOOL_CALL,
            data=ToolCallEventData(
                tool_call_id=tool_call_id, tool_name=tool_name, arguments=arguments or {}
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

    # 数据访问方法
    def get_final_message(self) -> FinalMessage | None:
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
        if self.type in (EventType.TEXT, EventType.THINKING):
            return self.data.get("content", "")
        if self.type == EventType.DONE:
            final_msg = self.get_final_message()
            if final_msg:
                return final_msg.content or final_msg.reasoning_content or ""
        return ""


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


class TerminationReason(str, Enum):
    """终止原因"""

    MAX_ITERATIONS = "max_iterations_exceeded"
    TOKEN_BUDGET = "token_budget_exceeded"
    TIMEOUT = "timeout"
    USER_CANCELLED = "user_cancelled"
    TASK_COMPLETE = "task_complete"
    ERROR = "error"


# ============================================================================
# 工具相关模型
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


class ToolDefinitionDict(TypedDict):
    """工具定义字典"""

    name: str
    description: str
    parameters: dict[str, Any]
    category: str
    requires_confirmation: bool


# ============================================================================
# Agent 执行限制常量（业务规则）
# ============================================================================


class AgentExecutionLimits:
    """Agent 执行限制常量（业务规则）

    集中管理 Agent 执行相关的限制值，便于统一调整和测试。
    """

    # 工具调用限制
    DEFAULT_MAX_TOOL_ITERATIONS: int = 10
    """单次对话中最大工具调用迭代次数"""

    # 执行超时
    DEFAULT_TIMEOUT_SECONDS: int = 300
    """Agent 执行超时时间（秒）"""

    # Agent 迭代限制
    DEFAULT_MAX_ITERATIONS: int = 20
    """Agent 最大迭代次数"""

    # Token 限制
    DEFAULT_MAX_TOKENS: int = 4096
    """单次响应最大 Token 数"""

    # 默认工具列表
    DEFAULT_TOOLS: ClassVar[list[str]] = [
        "read_file",
        "write_file",
        "list_dir",
        "run_shell",
        "search_code",
    ]
    """默认启用的工具列表"""

    # HITL 默认操作
    DEFAULT_HITL_OPERATIONS: ClassVar[list[str]] = [
        "run_shell",
        "write_file",
        "delete_file",
    ]
    """默认需要人工确认的操作"""


# ============================================================================
# Agent 配置和状态
# ============================================================================


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

    @classmethod
    def create_default(
        cls,
        name: str = "Default Agent",
        model: str | None = None,
        tools: list[str] | None = None,
        system_prompt: str | None = None,
        checkpoint_enabled: bool = True,
        hitl_enabled: bool = True,
    ) -> AgentConfig:
        """创建默认 Agent 配置

        提供业务规则定义的默认值，同时允许覆盖关键参数。

        Args:
            name: Agent 名称
            model: LLM 模型名称（默认使用 claude-3-5-sonnet）
            tools: 启用的工具列表（默认使用 DEFAULT_TOOLS）
            system_prompt: 系统提示
            checkpoint_enabled: 是否启用检查点
            hitl_enabled: 是否启用 HITL

        Returns:
            配置好的 AgentConfig 实例
        """
        return cls(
            name=name,
            model=model or "claude-3-5-sonnet-20241022",
            max_iterations=AgentExecutionLimits.DEFAULT_MAX_ITERATIONS,
            temperature=0.7,
            max_tokens=AgentExecutionLimits.DEFAULT_MAX_TOKENS,
            tools=tools if tools is not None else AgentExecutionLimits.DEFAULT_TOOLS.copy(),
            system_prompt=system_prompt,
            checkpoint_enabled=checkpoint_enabled,
            checkpoint_interval=5,
            hitl_enabled=hitl_enabled,
            hitl_operations=AgentExecutionLimits.DEFAULT_HITL_OPERATIONS.copy(),
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
    messages: list[Any] = Field(default_factory=list)  # list[Message]
    # 使用 SerializableDict 类型，提供运行时验证和序列化保证
    context: SerializableDict = Field(default_factory=dict)
    current_plan: list[str] | None = None
    iteration: int = 0
    total_tokens: int = 0
    pending_tool_call: SerializableDict | None = None
    completed: bool = False
    status: Literal["running", "paused", "completed", "error"] = "running"
    metadata: SerializableDict = Field(default_factory=dict)


# ============================================================================
# 检查点模型
# ============================================================================


class CheckpointMeta(BaseModel):
    """检查点元数据"""

    id: str
    session_id: str
    step: int
    created_at: datetime
    parent_id: str | None = None


class Checkpoint(BaseModel):
    """检查点"""

    model_config = ConfigDict()

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
# 类型别名
# ============================================================================

StateT = TypeVar("StateT", bound=BaseModel)

# 函数类型
ToolExecutor = Callable[..., Awaitable[ToolResult]]
NodeFunction = Callable[[AgentState], Awaitable[AgentState]]
ConditionFunction = Callable[[AgentState], str]
EventGenerator = "AsyncGenerator[AgentEvent, None]"

# JSON 类型
JSONSchema = dict[str, Any]

# ID 类型
UserId = str
AgentId = str
SessionId = str
MessageId = str
CheckpointId = str
