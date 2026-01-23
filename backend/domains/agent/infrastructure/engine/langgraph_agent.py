"""
LangGraph Agent Engine - 基于 LangGraph 的 Agent 执行引擎

使用 LangGraph StateGraph 和 checkpointer 实现：
- 对话历史管理（通过 checkpointer）
- 状态持久化
- 多会话支持（thread_id）
- 工具调用循环
"""

import asyncio
from collections.abc import AsyncGenerator
import operator
import time
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from domains.agent.domain.types import AgentConfig, AgentEvent, ToolCall, ToolResult
from domains.agent.infrastructure.engine.langgraph_checkpointer import LangGraphCheckpointer
from domains.agent.infrastructure.llm.gateway import LLMGateway
from domains.agent.infrastructure.llm.message_formatter import convert_langchain_messages
from domains.agent.infrastructure.memory.extractor import MemoryExtractor
from domains.agent.infrastructure.memory.langgraph_store import LongTermMemoryStore
from domains.agent.infrastructure.tools.registry import ToolRegistry
from libs.config import ExecutionConfig
from utils.logging import get_logger

logger = get_logger(__name__)

# 默认最大工具调用迭代次数
DEFAULT_MAX_TOOL_ITERATIONS = 10
# 默认超时时间（秒）
DEFAULT_TIMEOUT_SECONDS = 300


# 定义 Agent 状态（LangGraph 格式）
# 注意：LangGraph 要求状态必须是 TypedDict，无法使用 Pydantic 或 dataclass
class AgentState(TypedDict):
    """Agent 状态（LangGraph 格式）

    LangGraph StateGraph 要求状态必须是 TypedDict 或 dict。
    使用 StateView 包装类可以获得属性访问和类型安全。
    """

    messages: Annotated[list[BaseMessage], operator.add]
    user_id: str
    session_id: str
    iteration: int
    tool_iteration: int  # 工具调用迭代计数
    total_tokens: int
    recalled_memories: list[dict[str, Any]]
    pending_tool_calls: list[dict[str, Any]]  # 待处理的工具调用
    tool_results: list[dict[str, Any]]  # 工具执行结果
    reasoning_content: str | None  # 推理模型的思考内容


class StateView:
    """AgentState 的属性访问包装类

    提供属性访问方式，同时保持与 LangGraph TypedDict 的兼容。

    Usage:
        # 方式 1：字典访问（原始方式）
        user_id = state["user_id"]

        # 方式 2：属性访问（推荐）
        view = StateView(state)
        user_id = view.user_id
        if view.has_pending_tools:
            ...
    """

    __slots__ = ("_state",)  # 优化内存

    def __init__(self, state: AgentState) -> None:
        self._state = state

    # =========================================================================
    # 属性访问器 - 类型安全，IDE 自动补全
    # =========================================================================

    @property
    def messages(self) -> list[BaseMessage]:
        """消息列表"""
        return self._state["messages"]

    @property
    def user_id(self) -> str:
        """用户 ID"""
        return self._state["user_id"]

    @property
    def session_id(self) -> str:
        """会话 ID"""
        return self._state["session_id"]

    @property
    def iteration(self) -> int:
        """当前迭代次数"""
        return self._state["iteration"]

    @property
    def tool_iteration(self) -> int:
        """工具调用迭代次数"""
        return self._state["tool_iteration"]

    @property
    def total_tokens(self) -> int:
        """总 Token 数"""
        return self._state["total_tokens"]

    @property
    def recalled_memories(self) -> list[dict[str, Any]]:
        """召回的记忆"""
        return self._state["recalled_memories"]

    @property
    def pending_tool_calls(self) -> list[dict[str, Any]]:
        """待处理的工具调用"""
        return self._state["pending_tool_calls"]

    @property
    def tool_results(self) -> list[dict[str, Any]]:
        """工具执行结果"""
        return self._state["tool_results"]

    @property
    def reasoning_content(self) -> str | None:
        """推理内容（推理模型）"""
        return self._state["reasoning_content"]

    # =========================================================================
    # 辅助方法 - 业务逻辑
    # =========================================================================

    @property
    def has_pending_tools(self) -> bool:
        """是否有待处理的工具调用"""
        return len(self.pending_tool_calls) > 0

    @property
    def last_message_content(self) -> str:
        """最后一条消息的内容"""
        if self.messages:
            return self.messages[-1].content or ""
        return ""

    @property
    def has_memories(self) -> bool:
        """是否有召回的记忆"""
        return len(self.recalled_memories) > 0


class LangGraphAgentEngine:
    """
    基于 LangGraph 的 Agent 执行引擎

    使用 LangGraph StateGraph 和 checkpointer 实现：
    - 自动管理对话历史（通过 checkpointer）
    - 状态持久化
    - 多会话支持（thread_id = session_id）
    - 工具调用循环（LLM → 工具 → LLM）
    """

    def __init__(
        self,
        config: AgentConfig,
        llm_gateway: LLMGateway,
        memory_store: LongTermMemoryStore,
        tool_registry: ToolRegistry | None = None,
        checkpointer: LangGraphCheckpointer | None = None,
        max_tool_iterations: int = DEFAULT_MAX_TOOL_ITERATIONS,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        execution_config: ExecutionConfig | None = None,
    ) -> None:
        """
        初始化 LangGraph Agent Engine

        Args:
            config: Agent 配置
            llm_gateway: LLM 网关
            memory_store: 长期记忆存储
            tool_registry: 工具注册表
            checkpointer: 检查点管理器
            max_tool_iterations: 最大工具调用迭代次数
            timeout_seconds: 执行超时时间（秒）
            execution_config: 执行环境配置（可选）
        """
        self.config = config
        self.llm_gateway = llm_gateway
        self.memory_store = memory_store
        self.tools = tool_registry or ToolRegistry()
        self.max_tool_iterations = max_tool_iterations
        self.timeout_seconds = timeout_seconds
        self.execution_config = execution_config
        # 初始化记忆提取器
        self.memory_extractor = MemoryExtractor(llm_gateway=llm_gateway)

        # 初始化检查点管理器
        if checkpointer is None:
            logger.warning("No checkpointer provided, creating new one (this may cause issues!)")
            checkpointer = LangGraphCheckpointer(storage_type="postgres")
        self.checkpointer = checkpointer

        # 验证 checkpointer 是否已初始化
        inner_cp = self.checkpointer.get_checkpointer()
        logger.info(
            "LangGraphAgentEngine initialized with checkpointer type: %s, inner: %s",
            type(self.checkpointer).__name__,
            type(inner_cp).__name__ if inner_cp else "None",
        )

        # 构建 LangGraph
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        """
        构建 LangGraph 状态图

        图结构（支持工具调用循环）：
        START → recall_memory → call_llm → (条件判断)
                                    ↓
                             有工具调用？
                             ↓ Yes      ↓ No
                       execute_tools   extract_memory → END
                             ↓
                          call_llm (循环回来)
        """
        builder = StateGraph(AgentState)

        # 添加节点
        builder.add_node("recall_memory", self._recall_long_term_memory)
        builder.add_node("call_llm", self._call_llm)
        builder.add_node("execute_tools", self._execute_tools)
        builder.add_node("extract_memory", self._extract_memory)

        # 添加边
        builder.add_edge(START, "recall_memory")
        builder.add_edge("recall_memory", "call_llm")

        # 条件边：根据是否有工具调用决定下一步
        builder.add_conditional_edges(
            "call_llm",
            self._should_execute_tools,
            {
                "execute_tools": "execute_tools",
                "extract_memory": "extract_memory",
            },
        )

        # 工具执行后返回 LLM 继续处理
        builder.add_edge("execute_tools", "call_llm")

        # 记忆提取后结束
        builder.add_edge("extract_memory", END)

        # 编译图（使用检查点）
        return builder.compile(checkpointer=self.checkpointer.get_checkpointer())

    def _should_execute_tools(
        self, state: AgentState
    ) -> Literal["execute_tools", "extract_memory"]:
        """
        条件函数：判断是否需要执行工具

        Returns:
            "execute_tools": 如果有待处理的工具调用
            "extract_memory": 如果没有工具调用，进入记忆提取
        """
        # 使用 StateView 获得属性访问和辅助方法
        view = StateView(state)

        # 检查是否超过最大迭代次数
        if view.tool_iteration >= self.max_tool_iterations:
            logger.warning(
                "Tool iteration limit reached (%d), stopping tool execution",
                self.max_tool_iterations,
            )
            return "extract_memory"

        # 使用辅助属性检查工具调用
        if view.has_pending_tools:
            return "execute_tools"

        return "extract_memory"

    async def _recall_long_term_memory(self, state: AgentState) -> dict[str, Any]:
        """召回长期记忆（会话内长程记忆）

        记忆按 session_id 隔离，只检索当前会话的记忆。
        用于在长对话中召回早期的重要信息。

        注意：不跳过任何消息的检索，因为：
        - 短消息如 "?" "不对" 可能需要上下文理解
        - 向量检索成本很低（毫秒级）
        - SimpleMem 的过滤在存储阶段已完成，检索阶段应尽量召回
        """
        view = StateView(state)

        # 搜索当前会话的相关记忆
        memories = await self.memory_store.search(
            session_id=view.session_id,
            query=view.last_message_content,
            limit=5,
        )

        return {"recalled_memories": memories}

    async def _call_llm(self, state: AgentState) -> dict[str, Any]:
        """
        调用 LLM

        这是核心节点，负责：
        1. 构建消息列表（包含历史、工具结果等）
        2. 调用 LLM
        3. 解析响应（文本或工具调用）
        4. 记录推理内容（如果模型支持）
        """
        # 构建系统提示
        system_prompt = self.config.system_prompt or "你是一个有用的助手。"

        # 添加工具调用指导（防止无限循环）
        if self.config.tools:
            system_prompt += """

工具调用指南：
- 仔细分析用户请求，只在必要时调用工具
- 每次工具调用后，根据结果决定是否需要继续调用其他工具
- 当任务完成或获得足够信息时，立即生成最终回复，不要继续调用工具
- 如果工具调用失败，尝试其他方法或向用户说明情况"""

        # 使用 StateView 获得属性访问
        view = StateView(state)

        # 添加召回的记忆
        if view.has_memories:
            memory_text = "\n".join([f"- {m['content']}" for m in view.recalled_memories])
            system_prompt += f"\n\n相关记忆：\n{memory_text}"

        # 使用类型安全的消息转换（LangChain -> LiteLLM 格式）
        lite_messages = convert_langchain_messages(view.messages, system_prompt=system_prompt)

        # 获取工具定义
        tools = self.tools.to_openai_tools(self.config.tools) if self.config.tools else None

        # 调用 LiteLLM Gateway
        response = await self.llm_gateway.chat(
            messages=lite_messages,
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            tools=tools,
        )

        # 解析响应
        # 优先使用 content，若为空则使用 reasoning_content（推理模型兼容）
        final_content = response.content or response.reasoning_content or ""

        # 记录推理内容（用于事件发送）
        # 推理内容是独立的，不应与最终内容混淆
        reasoning_content = response.reasoning_content if response.reasoning_content else None

        if response.tool_calls:
            # LLM 请求调用工具
            # 将 ToolCall 对象转换为 LangChain 需要的字典格式
            tool_calls_dict = [
                {
                    "id": tc.id,
                    "name": tc.name,
                    "args": tc.arguments if isinstance(tc.arguments, dict) else {},
                }
                for tc in response.tool_calls
            ]

            # 返回带工具调用的 AI 消息，并设置待处理的工具调用
            # 包含 reasoning_content 供事件发送使用
            return {
                "messages": [AIMessage(content=final_content, tool_calls=tool_calls_dict)],
                "pending_tool_calls": tool_calls_dict,
                "tool_iteration": view.tool_iteration + 1,
                "reasoning_content": reasoning_content,  # 传递推理内容
            }

        # 返回纯文本响应，清空待处理的工具调用
        return {
            "messages": [AIMessage(content=final_content)],
            "pending_tool_calls": [],
            "reasoning_content": reasoning_content,  # 传递推理内容
        }

    async def _execute_tools(self, state: AgentState) -> dict[str, Any]:
        """
        并行执行工具

        对所有待处理的工具调用并行执行，显著提升多工具场景的响应速度。
        使用 asyncio.gather 实现并行，return_exceptions=True 确保单个失败不影响其他工具。
        """
        view = StateView(state)
        if not view.has_pending_tools:
            return {
                "messages": [],
                "pending_tool_calls": [],
                "tool_results": [],
            }

        # 构建 ToolCall 对象列表
        tool_calls = [
            ToolCall(
                id=tc_dict["id"],
                name=tc_dict["name"],
                arguments=tc_dict["args"] if isinstance(tc_dict["args"], dict) else {},
            )
            for tc_dict in view.pending_tool_calls
        ]

        # 并行执行所有工具（单个失败不影响其他工具）
        logger.info("Executing %d tools in parallel", len(tool_calls))
        results = await asyncio.gather(
            *[self._execute_single_tool(tc) for tc in tool_calls],
            return_exceptions=True,
        )

        # 处理结果
        tool_messages: list[ToolMessage] = []
        tool_results: list[dict[str, Any]] = []

        for tool_call, result in zip(tool_calls, results, strict=True):
            # 处理异常情况（asyncio.gather 返回异常对象）
            if isinstance(result, Exception):
                logger.error("Tool %s raised exception: %s", tool_call.name, result)
                result = ToolResult(
                    tool_call_id=tool_call.id,
                    success=False,
                    output="",
                    error=str(result),
                    duration_ms=0,
                )

            # 记录工具结果
            tool_results.append(
                {
                    "tool_call_id": tool_call.id,
                    "tool_name": tool_call.name,
                    "success": result.success,
                    "output": result.output,
                    "error": result.error,
                    "duration_ms": result.duration_ms,
                }
            )

            # 创建 ToolMessage
            if result.success:
                content = result.output
            else:
                error_msg = result.error or "Unknown error occurred"
                content = f"Error: {error_msg}"
                if result.output:
                    content += f"\nOutput: {result.output}"
            tool_messages.append(ToolMessage(content=content, tool_call_id=tool_call.id))

        logger.info(
            "Parallel tool execution completed: %d succeeded, %d failed",
            sum(1 for r in tool_results if r["success"]),
            sum(1 for r in tool_results if not r["success"]),
        )

        # 返回工具消息，清空待处理的工具调用
        return {
            "messages": tool_messages,
            "pending_tool_calls": [],
            "tool_results": tool_results,
        }

    async def _execute_single_tool(self, tool_call: ToolCall) -> ToolResult:
        """执行单个工具"""
        start_time = time.time()
        try:
            result = await self.tools.execute(tool_call.name, **tool_call.arguments)
            duration_ms = int((time.time() - start_time) * 1000)
            return result.model_copy(
                update={
                    "tool_call_id": tool_call.id,
                    "duration_ms": duration_ms,
                }
            )
        except Exception as e:
            logger.exception("Tool execution failed: %s - %s", tool_call.name, e)
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                output="",
                error=str(e),
                duration_ms=int((time.time() - start_time) * 1000),
            )

    async def _extract_memory(self, state: AgentState) -> dict[str, Any]:
        """提取并存储长期记忆

        注意：为避免重复提取，此节点的行为取决于配置：
        - 如果 simplemem_enabled=True：跳过此节点，由 ChatUseCase 后台调用 SimpleMem
        - 如果 simplemem_enabled=False：使用 MemoryExtractor 提取

        SimpleMem 有更好的过滤（novelty_threshold, skip_trivial）和混合检索（BM25+向量），
        所以推荐启用 SimpleMem 并让此节点跳过。
        """
        # pylint: disable=import-outside-toplevel
        from bootstrap.config import settings  # 避免循环导入

        # 如果启用了 SimpleMem，跳过此节点（由 ChatUseCase 异步处理）
        # 这样避免重复提取，SimpleMem 有更好的过滤机制
        if settings.simplemem_enabled:
            logger.debug("Skipping extract_memory: SimpleMem is enabled")
            return {}

        view = StateView(state)

        if not view.user_id or not self.memory_store:
            return {}

        # 构建对话历史（用于记忆提取）
        conversation = []
        for msg in view.messages:
            if isinstance(msg, HumanMessage):
                conversation.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                conversation.append({"role": "assistant", "content": msg.content})

        # 只有当对话包含多轮交互时才提取记忆（至少 2 轮）
        if len(conversation) >= 4:  # 至少 2 轮对话（每轮 2 条消息）
            try:
                # 使用 MemoryExtractor 提取并存储记忆
                await self.memory_extractor.extract_and_store(
                    memory_store=self.memory_store,
                    user_id=view.user_id,
                    conversation=conversation[-4:],  # 使用最近 2 轮对话
                    session_id=view.session_id,
                )
                logger.info("Extracted and stored memories for session %s", view.session_id)
            except Exception as e:
                logger.warning("Memory extraction failed: %s", e, exc_info=True)

        return {}

    def _handle_llm_node_event(
        self, node_output: dict[str, Any], current_iteration: int
    ) -> list[AgentEvent]:
        """处理 LLM 节点事件，返回推理和工具调用事件列表"""
        events = []
        reasoning = node_output.get("reasoning_content")
        if reasoning:
            events.append(
                AgentEvent.thinking(
                    status="reasoning",
                    iteration=current_iteration,
                    content=reasoning,
                )
            )

        pending_calls = node_output.get("pending_tool_calls", [])
        for tc in pending_calls:
            events.append(
                AgentEvent.tool_call(
                    tool_call_id=tc.get("id", ""),
                    tool_name=tc.get("name", ""),
                    arguments=tc.get("args", {}),
                )
            )

        return events

    def _handle_tools_node_event(
        self, node_output: dict[str, Any], current_iteration: int
    ) -> list[AgentEvent]:
        """处理工具执行节点事件，返回工具结果事件列表"""
        events = []
        if "tool_results" not in node_output:
            return events

        for tr in node_output["tool_results"]:
            events.append(
                AgentEvent.tool_result(
                    tool_call_id=tr["tool_call_id"],
                    tool_name=tr["tool_name"],
                    success=tr["success"],
                    output=tr["output"],
                    error=tr["error"],
                    duration_ms=tr["duration_ms"],
                )
            )

        events.append(AgentEvent.thinking(status="analyzing", iteration=current_iteration))
        return events

    def _extract_final_content(self, final_result: dict[str, Any]) -> tuple[str, str | None]:
        """从最终状态中提取内容和推理内容"""
        final_content = ""
        final_reasoning = final_result.get("reasoning_content")
        messages = final_result.get("messages", [])

        if not messages:
            if final_reasoning:
                final_content = final_reasoning
            return final_content, final_reasoning

        # 策略 1：从后往前找最后一条 AIMessage（非工具调用）
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                final_content = msg.content
                break

        # 策略 2：如果没找到非工具调用的消息，尝试获取最后一条 AIMessage 的 content
        if not final_content:
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and msg.content:
                    final_content = msg.content
                    break

        # 策略 3：如果仍然没有 content，使用 reasoning_content（推理模型兼容）
        if not final_content and final_reasoning:
            final_content = final_reasoning

        return final_content, final_reasoning

    async def run(
        self,
        session_id: str,
        user_id: str,
        user_message: str,
    ) -> AsyncGenerator[AgentEvent, None]:
        """
        执行 Agent

        业界最佳实践的事件流设计：
        1. thinking 事件 - 包含状态和推理内容（如果模型支持）
        2. tool_call 事件 - 包含工具名和参数
        3. tool_result 事件 - 包含结果或错误详情
        4. text 事件 - 最终回复内容
        5. done 事件 - 统计信息

        Args:
            session_id: 会话 ID（作为 LangGraph 的 thread_id，也用于记忆隔离）
            user_id: 用户 ID
            user_message: 用户消息

        Yields:
            AgentEvent: 执行事件流
        """
        # 获取 LangGraph 配置
        config = self.checkpointer.get_config(session_id)

        # 构建初始状态
        initial_state = {
            "messages": [HumanMessage(content=user_message)],
            "user_id": user_id,
            "session_id": session_id,
            "iteration": 0,
            "tool_iteration": 0,
            "total_tokens": 0,
            "recalled_memories": [],
            "pending_tool_calls": [],
            "tool_results": [],
            "reasoning_content": None,
        }

        # 发送初始思考事件（使用类型安全工厂方法）
        yield AgentEvent.thinking(status="processing", iteration=1)

        try:
            # 记录开始时间用于超时检查
            start_time = time.time()
            current_iteration = 0

            # 使用 astream 来获取中间状态，以便发送工具调用事件
            async for event in self.graph.astream(initial_state, config=config):
                # 检查是否超时
                elapsed = time.time() - start_time
                if elapsed > self.timeout_seconds:
                    logger.warning("Agent execution timed out after %.1f seconds", elapsed)
                    yield AgentEvent.error(f"执行超时（{self.timeout_seconds}秒）")
                    return

                # event 是一个字典，key 是节点名，value 是节点返回的状态更新
                for node_name, node_output in event.items():
                    if node_name == "call_llm":
                        current_iteration += 1
                        for evt in self._handle_llm_node_event(node_output, current_iteration):
                            yield evt

                    if node_name == "execute_tools":
                        for evt in self._handle_tools_node_event(node_output, current_iteration):
                            yield evt

            # astream 完成后，获取完整的最终状态
            # 注意：astream 返回的是增量更新，需要通过 get_state 获取完整状态
            final_state = await self.graph.aget_state(config)
            final_result = final_state.values if final_state else {}

            # 获取最后一条消息的内容
            final_content, final_reasoning = self._extract_final_content(final_result)

            # 发送文本事件
            if final_content:
                yield AgentEvent.text(final_content)

            # 发送完成事件（使用类型安全工厂方法）
            # 自动处理 reasoning_content
            yield AgentEvent.done(
                content=final_content,
                reasoning_content=final_reasoning if final_reasoning != final_content else None,
                iterations=current_iteration,
                tool_iterations=final_result.get("tool_iteration", 0),
                total_tokens=final_result.get("total_tokens", 0),
            )

        except TimeoutError as e:
            yield AgentEvent.error(str(e))
        except Exception as e:
            logger.exception("Agent execution error: %s", e)
            yield AgentEvent.error(str(e))
