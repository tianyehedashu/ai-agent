# Chat 消息流程分析

## 概述

本文档详细说明 AI Agent 聊天功能的消息处理流程，包括数据存储位置、消息构建方式以及各组件的职责。

---

## 消息流程图

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              完整消息流程                                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────┐                                                                │
│  │  前端 UI    │  用户输入: "我叫什么？"                                          │
│  └──────┬──────┘                                                                │
│         │                                                                       │
│         ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  API 请求                                                                │    │
│  │  POST /api/v1/chat                                                       │    │
│  │  Body: { message: "我叫什么？", session_id: "uuid-xxx" }                 │    │
│  └──────┬──────────────────────────────────────────────────────────────────┘    │
│         │                                                                       │
│         ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  ChatService.chat()                                                      │    │
│  │  - 验证/创建 session                                                     │    │
│  │  - 调用 LangGraphAgentEngine.run()                                       │    │
│  └──────┬──────────────────────────────────────────────────────────────────┘    │
│         │                                                                       │
│         ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  LangGraphAgentEngine.run()                                              │    │
│  │                                                                          │    │
│  │  initial_state = {                                                       │    │
│  │      "messages": [HumanMessage("我叫什么？")],  ← 只有当前消息            │    │
│  │      "user_id": "user-123",                                              │    │
│  │      "session_id": "uuid-xxx",                                           │    │
│  │      "recalled_memories": []                                             │    │
│  │  }                                                                       │    │
│  └──────┬──────────────────────────────────────────────────────────────────┘    │
│         │                                                                       │
│         ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  LangGraph.ainvoke(initial_state, config)                                │    │
│  │                                                                          │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐     │    │
│  │  │  Step 1: 从 Checkpointer 加载历史状态                            │     │    │
│  │  │                                                                  │     │    │
│  │  │  loaded_state["messages"] = [                                    │     │    │
│  │  │      HumanMessage("我叫张三"),        ← 历史消息                  │     │    │
│  │  │      AIMessage("你好张三！...")       ← 历史消息                  │     │    │
│  │  │  ]                                                               │     │    │
│  │  └─────────────────────────────────────────────────────────────────┘     │    │
│  │                              │                                           │    │
│  │                              ▼                                           │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐     │    │
│  │  │  Step 2: 合并状态 (使用 operator.add)                            │     │    │
│  │  │                                                                  │     │    │
│  │  │  merged_state["messages"] = [                                    │     │    │
│  │  │      HumanMessage("我叫张三"),        ← 来自 checkpointer         │     │    │
│  │  │      AIMessage("你好张三！..."),      ← 来自 checkpointer         │     │    │
│  │  │      HumanMessage("我叫什么？")       ← 来自 initial_state        │     │    │
│  │  │  ]                                                               │     │    │
│  │  └─────────────────────────────────────────────────────────────────┘     │    │
│  └──────┬──────────────────────────────────────────────────────────────────┘    │
│         │                                                                       │
│         ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  Node: recall_memory                                                     │    │
│  │  _recall_long_term_memory(state)                                         │    │
│  │                                                                          │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐     │    │
│  │  │  查询 Memory Store (向量数据库)                                   │     │    │
│  │  │                                                                  │     │    │
│  │  │  query = "我叫什么？"                                             │     │    │
│  │  │  results = vector_search(query, user_id)                         │     │    │
│  │  │                                                                  │     │    │
│  │  │  recalled_memories = [                                           │     │    │
│  │  │      {"content": "用户名字是张三", "type": "fact", ...}          │     │    │
│  │  │  ]                                                               │     │    │
│  │  └─────────────────────────────────────────────────────────────────┘     │    │
│  │                                                                          │    │
│  │  return {"recalled_memories": memories}                                  │    │
│  └──────┬──────────────────────────────────────────────────────────────────┘    │
│         │                                                                       │
│         ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  Node: process                                                           │    │
│  │  _process_message(state)                                                 │    │
│  │                                                                          │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐     │    │
│  │  │  构建发送给 LLM 的消息                                            │     │    │
│  │  │                                                                  │     │    │
│  │  │  # 1. 构建系统提示（每次重新构建，不存储）                         │     │    │
│  │  │  system_prompt = "你是一个有用的助手。"                           │     │    │
│  │  │  if recalled_memories:                                           │     │    │
│  │  │      system_prompt += "\n\n相关记忆：\n- 用户名字是张三"          │     │    │
│  │  │                                                                  │     │    │
│  │  │  # 2. 构建消息列表                                                │     │    │
│  │  │  history = state["messages"][:-1]  # 历史（不含当前）             │     │    │
│  │  │  current = state["messages"][-1]   # 当前消息                     │     │    │
│  │  │                                                                  │     │    │
│  │  │  lite_messages = [                                               │     │    │
│  │  │      {"role": "system", "content": system_prompt},  ← 动态构建   │     │    │
│  │  │      {"role": "user", "content": "我叫张三"},        ← history    │     │    │
│  │  │      {"role": "assistant", "content": "你好..."},   ← history    │     │    │
│  │  │      {"role": "user", "content": "我叫什么？"}       ← current    │     │    │
│  │  │  ]                                                               │     │    │
│  │  └─────────────────────────────────────────────────────────────────┘     │    │
│  │                              │                                           │    │
│  │                              ▼                                           │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐     │    │
│  │  │  调用 LLM Gateway                                                │     │    │
│  │  │                                                                  │     │    │
│  │  │  response = await llm_gateway.chat(                              │     │    │
│  │  │      messages=lite_messages,                                     │     │    │
│  │  │      model="deepseek-reasoner",                                  │     │    │
│  │  │      tools=[...]                                                 │     │    │
│  │  │  )                                                               │     │    │
│  │  │                                                                  │     │    │
│  │  │  LLM 返回: "你叫张三。"                                           │     │    │
│  │  └─────────────────────────────────────────────────────────────────┘     │    │
│  │                                                                          │    │
│  │  return {"messages": [AIMessage("你叫张三。")]}  ← 追加到 state         │    │
│  └──────┬──────────────────────────────────────────────────────────────────┘    │
│         │                                                                       │
│         ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  Node: extract_memory                                                    │    │
│  │  _extract_memory(state)                                                  │    │
│  │                                                                          │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐     │    │
│  │  │  从对话中提取长期记忆（仅当对话 >= 4 条消息时）                    │     │    │
│  │  │                                                                  │     │    │
│  │  │  conversation = [                                                │     │    │
│  │  │      {"role": "user", "content": "我叫张三"},                     │     │    │
│  │  │      {"role": "assistant", "content": "你好张三！..."},           │     │    │
│  │  │      {"role": "user", "content": "我叫什么？"},                   │     │    │
│  │  │      {"role": "assistant", "content": "你叫张三。"}               │     │    │
│  │  │  ]                                                               │     │    │
│  │  │                                                                  │     │    │
│  │  │  → 调用 MemoryExtractor 提取并存储到 Memory Store                 │     │    │
│  │  └─────────────────────────────────────────────────────────────────┘     │    │
│  │                                                                          │    │
│  │  return {}  # 不修改 state                                               │    │
│  └──────┬──────────────────────────────────────────────────────────────────┘    │
│         │                                                                       │
│         ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  LangGraph 完成                                                          │    │
│  │                                                                          │    │
│  │  final_state["messages"] = [                                             │    │
│  │      HumanMessage("我叫张三"),                                           │    │
│  │      AIMessage("你好张三！..."),                                         │    │
│  │      HumanMessage("我叫什么？"),                                         │    │
│  │      AIMessage("你叫张三。")        ← 新增的 AI 响应                      │    │
│  │  ]                                                                       │    │
│  │                                                                          │    │
│  │  → 自动保存到 Checkpointer (AsyncPostgresSaver)                          │    │
│  └──────┬──────────────────────────────────────────────────────────────────┘    │
│         │                                                                       │
│         ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │  SSE 响应流                                                              │    │
│  │                                                                          │    │
│  │  data: {"type": "session_created", "data": {"session_id": "..."}}        │    │
│  │  data: {"type": "thinking", "data": {"status": "processing"}}            │    │
│  │  data: {"type": "text", "data": {"content": "你叫张三。"}}               │    │
│  │  data: {"type": "done", "data": {"final_message": {...}}}                │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 数据存储位置

| 数据类型 | 存储位置 | 持久化 | 说明 |
|----------|----------|--------|------|
| **对话历史** | LangGraph Checkpointer (PostgreSQL) | ✅ 是 | 通过 `state["messages"]` 自动管理 |
| **长期记忆** | Memory Store (向量数据库) | ✅ 是 | 跨会话的持久信息，通过语义搜索召回 |
| **系统提示** | 不存储，每次动态构建 | ❌ 否 | 在 `_process_message` 中构建 |
| **召回记忆** | 临时存储在 `state["recalled_memories"]` | ❌ 否 | 每次请求重新搜索 |

---

## 系统提示词处理

### 系统提示词不会重复记录

```python
# _process_message 方法中的处理
async def _process_message(self, state: AgentState) -> dict[str, Any]:
    # 1. 每次调用都重新构建系统提示（不从 state 读取）
    system_prompt = self.config.system_prompt or "你是一个有用的助手。"

    # 2. 添加召回的记忆（也是每次重新构建）
    recalled_memories = state.get("recalled_memories", [])
    if recalled_memories:
        memory_text = "\n".join([f"- {m['content']}" for m in recalled_memories])
        system_prompt += f"\n\n相关记忆：\n{memory_text}"

    # 3. 构建消息列表（系统提示作为第一条）
    lite_messages = [{"role": "system", "content": system_prompt}]

    # 4. 历史消息只包含 HumanMessage 和 AIMessage
    for msg in history:
        if isinstance(msg, HumanMessage):
            lite_messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            lite_messages.append({"role": "assistant", "content": msg.content})
```

### 关键点

1. **系统提示不存储在 `state["messages"]`** - 它是在每次 `_process_message` 调用时动态构建的
2. **`state["messages"]` 只包含用户和助手消息** - `HumanMessage` 和 `AIMessage`
3. **召回记忆追加到系统提示** - 不作为单独的消息发送

---

## 系统提示词每次都会发送

### 为什么每次请求都要发送系统提示词？

**LLM API 是无状态的** - OpenAI、DeepSeek、Claude 等 API 不会记住之前的对话，每次调用都是独立的请求。

### 多轮对话示例

```
第一次请求（用户说"我叫张三"）：
┌────────────────────────────────────────────────────────────┐
│ {"role": "system", "content": "你是一个有用的助手。"}       │ ← 系统提示
│ {"role": "user", "content": "我叫张三"}                    │ ← 用户消息
└────────────────────────────────────────────────────────────┘

第二次请求（用户问"我叫什么？"）：
┌────────────────────────────────────────────────────────────┐
│ {"role": "system", "content": "你是一个有用的助手。"}       │ ← 系统提示（再次发送）
│ {"role": "user", "content": "我叫张三"}                    │ ← 历史消息
│ {"role": "assistant", "content": "你好张三！"}             │ ← 历史消息
│ {"role": "user", "content": "我叫什么？"}                  │ ← 当前消息
└────────────────────────────────────────────────────────────┘

第三次请求（用户问"今天天气怎么样？"）：
┌────────────────────────────────────────────────────────────┐
│ {"role": "system", "content": "你是一个有用的助手。"}       │ ← 系统提示（再次发送）
│ {"role": "user", "content": "我叫张三"}                    │ ← 历史消息
│ {"role": "assistant", "content": "你好张三！"}             │ ← 历史消息
│ {"role": "user", "content": "我叫什么？"}                  │ ← 历史消息
│ {"role": "assistant", "content": "你叫张三。"}             │ ← 历史消息
│ {"role": "user", "content": "今天天气怎么样？"}            │ ← 当前消息
└────────────────────────────────────────────────────────────┘
```

### 这是行业标准

| 原因 | 说明 |
|------|------|
| **LLM API 无状态** | API 不记住之前的对话，每次都是独立请求 |
| **系统提示必须包含** | 如果不发送，LLM 不知道自己的角色和行为准则 |
| **所有应用都这样做** | ChatGPT、Claude、Cursor 等都是这样实现的 |

### Token 消耗影响

系统提示词会在每次请求中消耗 token：

```
"你是一个有用的助手。" ≈ 10-15 tokens

如果对话 10 轮，系统提示累计消耗：10 × 15 = 150 tokens
```

### 优化建议

如果系统提示词较长，可以考虑：

1. **精简系统提示** - 使用更短的措辞
2. **Prompt Caching** - 部分 LLM 支持（如 Anthropic Claude）
3. **分层提示** - 核心指令放系统提示，详细说明放用户消息

---

## AgentState 定义

```python
class AgentState(TypedDict):
    """Agent 状态（LangGraph 格式）"""

    # 对话消息（使用 operator.add 实现追加合并）
    messages: Annotated[list[BaseMessage], operator.add]

    # 用户和会话信息
    user_id: str
    session_id: str

    # 执行状态
    iteration: int
    total_tokens: int

    # 召回的记忆（每次请求重新搜索，不持久化）
    recalled_memories: list[dict[str, Any]]
```

### messages 合并机制

```python
# AgentState 定义
messages: Annotated[list[BaseMessage], operator.add]

# 当 LangGraph 执行时：
# 1. 从 checkpointer 加载: [msg1, msg2]
# 2. initial_state 输入: [msg3]
# 3. 合并结果: [msg1, msg2, msg3]  (使用 operator.add)
```

---

## 潜在的信息冗余

### 场景描述

当 Memory Store 中存储了之前提取的记忆时，可能出现信息冗余：

```
发送给 LLM 的完整内容：

┌─────────────────────────────────────────────────────────────┐
│ System Prompt:                                              │
│ "你是一个有用的助手。                                        │
│                                                             │
│ 相关记忆：                                                   │
│ - 用户名字是张三"                    ← 来自 Memory Store    │
├─────────────────────────────────────────────────────────────┤
│ Messages:                                                   │
│ [user]: "我叫张三"                   ← 来自 Checkpointer    │
│ [assistant]: "你好张三！..."         ← 来自 Checkpointer    │
│ [user]: "我叫什么？"                 ← 当前消息             │
└─────────────────────────────────────────────────────────────┘
```

### 说明

- **这不是重复发送** - 系统提示和对话历史是不同的数据来源
- **设计如此** - Memory Store 用于跨会话的长期记忆
- **可以优化** - 如果需要减少冗余，可以在有历史消息时跳过 memory 召回

---

## 优化建议

### 1. 减少当前会话的记忆召回

```python
async def _recall_long_term_memory(self, state: AgentState) -> dict[str, Any]:
    """召回长期记忆"""
    # 如果已有对话历史，不召回记忆（避免与历史重复）
    if len(state["messages"]) > 1:
        return {"recalled_memories": []}

    # 只在新会话时召回记忆
    memories = await self.memory_store.search(
        user_id=state.get("user_id", ""),
        query=state["messages"][-1].content,
        limit=5,
    )
    return {"recalled_memories": memories}
```

### 2. 排除当前会话的记忆

```python
async def _recall_long_term_memory(self, state: AgentState) -> dict[str, Any]:
    """召回长期记忆"""
    session_id = state.get("session_id", "")

    memories = await self.memory_store.search(
        user_id=state.get("user_id", ""),
        query=state["messages"][-1].content,
        limit=5,
        exclude_session_id=session_id,  # 排除当前会话的记忆
    )
    return {"recalled_memories": memories}
```

---

## 相关文件

| 文件 | 说明 |
|------|------|
| `backend/core/engine/langgraph_agent.py` | LangGraph Agent 实现 |
| `backend/core/engine/langgraph_checkpointer.py` | Checkpointer 封装 |
| `backend/core/memory/langgraph_store.py` | 长期记忆存储 |
| `backend/core/memory/extractor.py` | 记忆提取器 |
| `backend/services/chat.py` | Chat 服务层 |
| `backend/api/v1/chat.py` | Chat API 端点 |
| `frontend/src/hooks/use-chat.ts` | 前端 Chat Hook |
| `frontend/src/api/chat.ts` | 前端 Chat API |
