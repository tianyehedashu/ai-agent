# 本项目上下文管理实施方案

> 基于当前架构的最佳实践指南
> 更新日期：2026-01-16

## 1. 当前架构分析

### 1.1 核心组件

```
┌─────────────────────────────────────────────────────────────────┐
│                      当前架构                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ChatService (服务层)                                            │
│       │                                                          │
│       ▼                                                          │
│  LangGraphAgentEngine (执行引擎)                                 │
│       │                                                          │
│       ├── LangGraph Checkpointer (对话历史持久化)               │
│       ├── LongTermMemoryStore (长期记忆 - 向量检索)             │
│       ├── MemoryExtractor (记忆提取)                            │
│       └── LLMGateway (LLM 调用)                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 已有能力

| 组件 | 能力 | 状态 |
|------|------|------|
| `LangGraph Checkpointer` | 对话历史持久化 | ✅ 已实现 |
| `LongTermMemoryStore` | 向量检索记忆 | ✅ 已实现 |
| `MemoryExtractor` | 从对话提取记忆 | ✅ 已实现 |
| `SmartContextCompressor` | 智能压缩 | ✅ 已实现 |
| `KeyMessageDetector` | 关键消息检测 | ✅ 已实现 |
| `PlanTracker` | 计划追踪 | ✅ 已实现 |
| `PromptCacheManager` | 提示词缓存 | ✅ 已实现 |

### 1.3 待集成点

当前 `LangGraphAgentEngine._call_llm` 方法直接构建消息列表，缺少：
- 智能上下文压缩
- 关键消息检测
- 计划感知压缩
- 提示词缓存

## 2. 实施方案

### 2.1 架构改进

```
┌─────────────────────────────────────────────────────────────────┐
│                      改进后架构                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ChatService                                                     │
│       │                                                          │
│       ▼                                                          │
│  LangGraphAgentEngine                                            │
│       │                                                          │
│       ├── SmartContextManager (新增 - 统一管理)                 │
│       │       │                                                  │
│       │       ├── KeyMessageDetector (关键消息检测)             │
│       │       ├── PlanTracker (计划追踪)                        │
│       │       ├── SmartContextCompressor (智能压缩)             │
│       │       └── PromptCacheManager (提示词缓存)               │
│       │                                                          │
│       ├── LangGraph Checkpointer                                 │
│       ├── LongTermMemoryStore                                    │
│       └── LLMGateway                                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 新增组件：SmartContextManager

创建统一的上下文管理器，整合所有智能上下文组件：

```python
# core/context/smart_manager.py

class SmartContextManager:
    """
    智能上下文管理器

    整合关键消息检测、计划追踪、智能压缩、提示词缓存
    """

    def __init__(
        self,
        llm_gateway: LLMGateway,
        config: SmartContextConfig,
    ):
        self.key_detector = KeyMessageDetector()
        self.plan_tracker = PlanTracker()
        self.compressor = SmartContextCompressor(llm_gateway)
        self.cache_manager = PromptCacheManager()

        # 固定记忆（永不删除）
        self.pinned_memories: list[Message] = []

    async def build_context(
        self,
        messages: list[BaseMessage],
        recalled_memories: list[dict],
        system_prompt: str,
        model: str,
    ) -> list[dict[str, Any]]:
        """
        构建优化后的上下文

        流程：
        1. 检测关键消息 → 固定
        2. 更新计划状态 → 判断阶段
        3. 智能压缩 → 保留重要内容
        4. 应用提示词缓存 → 优化成本
        """
        pass
```

## 3. 具体实施步骤

### Phase 1: 集成智能压缩（1-2 天）

**目标**: 在 `_call_llm` 中使用 `SmartContextCompressor`

**修改文件**: `core/engine/langgraph_agent.py`

```python
# 在 __init__ 中添加
from core.context import SmartContextCompressor, CompressionConfig

def __init__(self, ...):
    # ... 现有代码

    # 新增：智能压缩器
    self.compressor = SmartContextCompressor(
        llm_gateway=llm_gateway,
        config=CompressionConfig(
            max_history_tokens=80000,
            protect_first_n_turns=2,
            protect_last_n_messages=6,
        ),
    )

# 在 _call_llm 中使用
async def _call_llm(self, state: AgentState) -> dict[str, Any]:
    # 转换消息为 Message 类型
    messages = self._convert_to_messages(state["messages"])

    # 智能压缩
    result = await self.compressor.compress(messages, budget_tokens=80000)

    # 构建消息列表
    lite_messages = [{"role": "system", "content": system_prompt}]

    # 如果有摘要，添加为系统消息
    if result.summary:
        lite_messages.append({
            "role": "system",
            "content": f"[之前对话摘要]\n{result.summary}"
        })

    # 添加压缩后的消息
    for msg in result.messages:
        lite_messages.append(self._format_message(msg))

    # ... 继续调用 LLM
```

### Phase 2: 集成关键消息检测（1 天）

**目标**: 识别并保护任务定义、约束等关键消息

**修改文件**: `core/engine/langgraph_agent.py`

```python
from core.context import KeyMessageDetector, get_key_detector

def __init__(self, ...):
    # ... 现有代码
    self.key_detector = get_key_detector()
    self._pinned_messages: list[int] = []  # 固定消息索引

async def _call_llm(self, state: AgentState) -> dict[str, Any]:
    messages = state["messages"]

    # 检测关键消息
    for i, msg in enumerate(messages):
        if i not in self._pinned_messages:
            result = self.key_detector.detect(
                self._to_core_message(msg),
                i,
                len(messages)
            )
            if result.should_pin:
                self._pinned_messages.append(i)
                logger.info("Pinned message %d: %s", i, result.types)

    # 压缩时保护固定消息
    # ...
```

### Phase 3: 集成计划追踪（2 天）

**目标**: 实现计划感知的上下文管理

**修改文件**: `core/engine/langgraph_agent.py`

```python
from core.context import PlanTracker

def __init__(self, ...):
    # ... 现有代码
    self.plan_tracker = PlanTracker()

async def _call_llm(self, state: AgentState) -> dict[str, Any]:
    messages = state["messages"]

    # 尝试从消息中提取计划
    if not self.plan_tracker.has_plan:
        self.plan_tracker.extract_plan_from_messages(
            [self._to_core_message(m) for m in messages]
        )

    # 检查阶段变更
    if self.plan_tracker.phase_changed:
        # 阶段变更时触发更积极的压缩
        logger.info("Phase changed, triggering compression")
        self.plan_tracker.reset_phase_changed()

    # 计算消息与计划的相关性
    for i, msg in enumerate(messages):
        relevance = self.plan_tracker.get_message_relevance(
            i, msg.content or ""
        )
        # 相关性低的消息优先被压缩

    # ...
```

### Phase 4: 集成提示词缓存（1 天）

**目标**: 利用云厂商的缓存 API 降低成本

**修改文件**: `core/llm/gateway.py`

```python
from core.llm.prompt_cache import get_prompt_cache_manager

async def chat(self, messages, model, ...):
    # 应用提示词缓存
    cache_manager = get_prompt_cache_manager()
    if cache_manager.is_cache_supported(model):
        messages = cache_manager.prepare_cacheable_messages(messages, model)

    # 调用 LLM
    response = await self._chat(**kwargs)

    # 更新缓存统计
    if response.usage:
        provider = cache_manager.get_provider_from_model(model)
        cache_manager.update_stats(response.usage, provider)

    return response
```

### Phase 5: 创建统一管理器（2 天）

**目标**: 创建 `SmartContextManager` 统一管理所有组件

创建新文件 `core/context/smart_manager.py`，整合所有功能。

## 4. 配置建议

### 4.1 环境变量

在 `.env` 中添加：

```bash
# 智能上下文管理
SMART_CONTEXT_ENABLED=true
CONTEXT_COMPRESSION_THRESHOLD=0.7
CONTEXT_MAX_HISTORY_TOKENS=80000
CONTEXT_PROTECT_FIRST_TURNS=2
CONTEXT_PROTECT_LAST_MESSAGES=6

# 提示词缓存
PROMPT_CACHE_ENABLED=true

# 记忆摘要
MEMORY_SUMMARIZATION_ENABLED=true
MEMORY_SUMMARIZATION_THRESHOLD=8000
```

### 4.2 配置类

在 `app/config.py` 中已添加：

```python
# Token 优化配置
prompt_cache_enabled: bool = True
memory_summarization_enabled: bool = True
memory_summarization_threshold: int = 8000
tiered_memory_enabled: bool = True
```

## 5. 监控与评估

### 5.1 添加监控指标

```python
# 在 LangGraphAgentEngine 中添加
class ContextMetrics:
    """上下文管理指标"""

    def __init__(self):
        self.total_messages = 0
        self.compressed_messages = 0
        self.pinned_messages = 0
        self.summary_generated = 0
        self.tokens_saved = 0
        self.cache_hits = 0
        self.cache_misses = 0

    def to_dict(self) -> dict:
        return {
            "compression_ratio": self.compressed_messages / max(1, self.total_messages),
            "tokens_saved": self.tokens_saved,
            "cache_hit_rate": self.cache_hits / max(1, self.cache_hits + self.cache_misses),
            "pinned_messages": self.pinned_messages,
        }
```

### 5.2 日志记录

```python
# 在关键点添加日志
logger.info(
    "Context optimization: original=%d, compressed=%d, pinned=%d, summary=%s",
    len(original_messages),
    len(compressed_messages),
    len(self._pinned_messages),
    "yes" if result.summary else "no",
)
```

## 6. 测试方案

### 6.1 单元测试

```python
# tests/core/context/test_smart_compressor.py

async def test_compression_preserves_pinned():
    """测试压缩保留固定消息"""
    compressor = SmartContextCompressor(mock_llm)
    messages = create_test_messages(20)

    result = await compressor.compress(messages, budget_tokens=5000)

    # 验证首轮消息被保留
    assert messages[0] in result.messages
    assert messages[1] in result.messages

async def test_compression_generates_summary():
    """测试压缩生成摘要"""
    compressor = SmartContextCompressor(mock_llm)
    messages = create_long_conversation(50)

    result = await compressor.compress(messages, budget_tokens=5000)

    assert result.summary is not None
    assert result.compression_ratio > 0.5
```

### 6.2 集成测试

```python
# tests/integration/test_context_management.py

async def test_long_conversation_context():
    """测试长对话的上下文管理"""
    engine = create_test_engine()

    # 模拟 30 轮对话
    for i in range(30):
        response = await engine.run(
            session_id="test",
            user_id="user1",
            user_message=f"第 {i+1} 轮对话",
        )

    # 验证任务定义仍被理解
    response = await engine.run(
        session_id="test",
        user_id="user1",
        user_message="请总结我们最初的任务目标",
    )

    # 应该能正确回忆任务定义
    assert "任务目标" in response.content
```

## 7. 实施优先级

| 优先级 | 任务 | 预计时间 | 预期收益 |
|--------|------|----------|----------|
| **P0** | 集成 SmartContextCompressor | 1-2 天 | Token 节省 50%+ |
| **P0** | 集成 KeyMessageDetector | 1 天 | 保留任务定义 |
| **P1** | 集成 PromptCacheManager | 1 天 | 成本降低 50%-90% |
| **P1** | 集成 PlanTracker | 2 天 | 智能选择保留内容 |
| **P2** | 创建 SmartContextManager | 2 天 | 统一管理 |
| **P2** | 添加监控指标 | 1 天 | 可观测性 |

## 8. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 摘要丢失关键信息 | 任务理解偏差 | 关键消息检测 + 固定保护 |
| 压缩延迟 | 响应变慢 | 异步压缩 + 缓存 |
| 计划提取失败 | 降级到简单压缩 | 提供回退策略 |
| 缓存不命中 | 成本未降低 | 监控命中率 + 优化提示词结构 |

## 9. 回滚方案

如果新功能出现问题，可以通过配置快速回滚：

```python
# 通过配置禁用新功能
SMART_CONTEXT_ENABLED=false  # 禁用智能压缩
PROMPT_CACHE_ENABLED=false   # 禁用提示词缓存

# 代码中检查
if settings.smart_context_enabled:
    # 使用智能压缩
    result = await self.compressor.compress(messages)
else:
    # 降级到简单滑动窗口
    result = self._simple_trim(messages)
```
