"""
LangGraph Agent Engine - 基于 LangGraph 的 Agent 执行引擎

使用 LangGraph StateGraph 和 checkpointer 实现：
- 对话历史管理（通过 checkpointer）
- 状态持久化
- 多会话支持（thread_id）
- 工具调用循环
"""

from collections.abc import AsyncGenerator
import json
import operator
import time
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from core.config import ExecutionConfig
from core.engine.langgraph_checkpointer import LangGraphCheckpointer
from core.llm.gateway import LLMGateway
from core.memory.extractor import MemoryExtractor
from core.memory.langgraph_store import LongTermMemoryStore
from core.types import AgentConfig, AgentEvent, EventType, ToolCall, ToolResult
from tools.registry import ToolRegistry
from utils.logging import get_logger

logger = get_logger(__name__)

# 默认最大工具调用迭代次数
DEFAULT_MAX_TOOL_ITERATIONS = 10
# 默认超时时间（秒）
DEFAULT_TIMEOUT_SECONDS = 300


# 定义 Agent 状态（LangGraph 格式）
class AgentState(TypedDict):
    """Agent 状态（LangGraph 格式）"""

    messages: Annotated[list[BaseMessage], operator.add]
    user_id: str
    session_id: str
    iteration: int
    tool_iteration: int  # 工具调用迭代计数
    total_tokens: int
    recalled_memories: list[dict[str, Any]]
    pending_tool_calls: list[dict[str, Any]]  # 待处理的工具调用
    tool_results: list[dict[str, Any]]  # 工具执行结果


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
        pending_tool_calls = state.get("pending_tool_calls", [])
        tool_iteration = state.get("tool_iteration", 0)

        # 检查是否超过最大迭代次数
        if tool_iteration >= self.max_tool_iterations:
            logger.warning(
                "Tool iteration limit reached (%d), stopping tool execution",
                self.max_tool_iterations,
            )
            return "extract_memory"

        # 检查是否有待处理的工具调用
        if pending_tool_calls:
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
        session_id = state.get("session_id", "")
        last_message = state["messages"][-1].content if state["messages"] else ""

        # 搜索当前会话的相关记忆
        memories = await self.memory_store.search(
            session_id=session_id,
            query=last_message,
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

        # 添加召回的记忆
        recalled_memories = state.get("recalled_memories", [])
        if recalled_memories:
            memory_text = "\n".join([f"- {m['content']}" for m in recalled_memories])
            system_prompt += f"\n\n相关记忆：\n{memory_text}"

        # 构建消息列表（LiteLLM 格式）
        lite_messages = [{"role": "system", "content": system_prompt}]

        # 添加所有消息（包括历史、工具调用、工具结果）
        for msg in state["messages"]:
            if isinstance(msg, HumanMessage):
                lite_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                msg_dict: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
                # 如果有工具调用，添加到消息中
                if msg.tool_calls:
                    msg_dict["tool_calls"] = [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                # 使用 json.dumps 确保参数是有效的 JSON 字符串
                                "arguments": (
                                    tc["args"]
                                    if isinstance(tc["args"], str)
                                    else json.dumps(tc["args"], ensure_ascii=False)
                                ),
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                lite_messages.append(msg_dict)
            elif isinstance(msg, ToolMessage):
                lite_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id,
                        "content": msg.content,
                    }
                )

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
            return {
                "messages": [AIMessage(content=final_content, tool_calls=tool_calls_dict)],
                "pending_tool_calls": tool_calls_dict,
                "tool_iteration": state.get("tool_iteration", 0) + 1,
            }

        # 返回纯文本响应，清空待处理的工具调用
        return {
            "messages": [AIMessage(content=final_content)],
            "pending_tool_calls": [],
        }

    async def _execute_tools(self, state: AgentState) -> dict[str, Any]:
        """
        执行工具

        执行所有待处理的工具调用，并将结果作为 ToolMessage 返回
        """
        pending_tool_calls = state.get("pending_tool_calls", [])
        tool_messages: list[ToolMessage] = []
        tool_results: list[dict[str, Any]] = []

        for tc_dict in pending_tool_calls:
            # 创建 ToolCall 对象
            tool_call = ToolCall(
                id=tc_dict["id"],
                name=tc_dict["name"],
                arguments=tc_dict["args"] if isinstance(tc_dict["args"], dict) else {},
            )

            # 执行工具
            result = await self._execute_single_tool(tool_call)

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
                # 确保错误信息有意义
                error_msg = result.error or "Unknown error occurred"
                content = f"Error: {error_msg}"
                if result.output:
                    content += f"\nOutput: {result.output}"
            tool_messages.append(ToolMessage(content=content, tool_call_id=tool_call.id))

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
        - 如果 simplemem_enabled=True：跳过此节点，由 ChatService 后台调用 SimpleMem
        - 如果 simplemem_enabled=False：使用 MemoryExtractor 提取

        SimpleMem 有更好的过滤（novelty_threshold, skip_trivial）和混合检索（BM25+向量），
        所以推荐启用 SimpleMem 并让此节点跳过。
        """
        # pylint: disable=import-outside-toplevel
        from app.config import settings  # 避免循环导入

        # 如果启用了 SimpleMem，跳过此节点（由 ChatService 异步处理）
        # 这样避免重复提取，SimpleMem 有更好的过滤机制
        if settings.simplemem_enabled:
            logger.debug("Skipping extract_memory: SimpleMem is enabled")
            return {}

        user_id = state.get("user_id", "")
        session_id = state.get("session_id", "")

        if not user_id or not self.memory_store:
            return {}

        # 构建对话历史（用于记忆提取）
        conversation = []
        for msg in state["messages"]:
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
                    user_id=user_id,
                    conversation=conversation[-4:],  # 使用最近 2 轮对话
                    session_id=session_id,
                )
                logger.info("Extracted and stored memories for session %s", session_id)
            except Exception as e:
                logger.warning("Memory extraction failed: %s", e, exc_info=True)

        return {}

    async def run(
        self,
        session_id: str,
        user_id: str,
        user_message: str,
    ) -> AsyncGenerator[AgentEvent, None]:
        """
        执行 Agent

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
        }

        # 发送思考事件
        yield AgentEvent(
            type=EventType.THINKING,
            data={"status": "processing"},
        )

        try:
            # 记录开始时间用于超时检查
            start_time = time.time()

            # 使用 astream 来获取中间状态，以便发送工具调用事件
            async for event in self.graph.astream(initial_state, config=config):
                # 检查是否超时
                elapsed = time.time() - start_time
                if elapsed > self.timeout_seconds:
                    logger.warning("Agent execution timed out after %.1f seconds", elapsed)
                    yield AgentEvent(
                        type=EventType.ERROR,
                        data={"error": f"执行超时（{self.timeout_seconds}秒）"},
                    )
                    return

                # event 是一个字典，key 是节点名，value 是节点返回的状态更新
                for node_name, node_output in event.items():
                    # 处理工具执行事件
                    if node_name == "execute_tools" and "tool_results" in node_output:
                        for tr in node_output["tool_results"]:
                            # 发送工具调用事件
                            yield AgentEvent(
                                type=EventType.TOOL_CALL,
                                data={
                                    "tool_call_id": tr["tool_call_id"],
                                    "tool_name": tr["tool_name"],
                                },
                            )
                            # 发送工具结果事件
                            yield AgentEvent(
                                type=EventType.TOOL_RESULT,
                                data={
                                    "tool_call_id": tr["tool_call_id"],
                                    "success": tr["success"],
                                    "output": tr["output"],
                                    "error": tr["error"],
                                    "duration_ms": tr["duration_ms"],
                                },
                            )

            # astream 完成后，获取完整的最终状态
            # 注意：astream 返回的是增量更新，需要通过 get_state 获取完整状态
            final_state = await self.graph.aget_state(config)
            final_result = final_state.values if final_state else {}

            # 获取最后一条消息
            final_content = ""
            messages = final_result.get("messages", [])
            if messages:
                # 从后往前找最后一条 AIMessage（非工具调用）
                for msg in reversed(messages):
                    if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                        final_content = msg.content
                        break

            # 发送文本事件
            if final_content:
                yield AgentEvent(
                    type=EventType.TEXT,
                    data={"content": final_content},
                )

            # 发送完成事件（包含 final_message 供前端使用）
            yield AgentEvent(
                type=EventType.DONE,
                data={
                    "iterations": final_result.get("iteration", 0),
                    "tool_iterations": final_result.get("tool_iteration", 0),
                    "total_tokens": final_result.get("total_tokens", 0),
                    "final_message": {"content": final_content},
                },
            )

        except Exception as e:
            logger.exception("Agent execution error: %s", e)
            yield AgentEvent(
                type=EventType.ERROR,
                data={"error": str(e)},
            )
