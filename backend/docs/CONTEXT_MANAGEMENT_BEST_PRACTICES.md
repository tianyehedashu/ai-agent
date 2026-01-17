# Agent 上下文管理最佳实践

> 基于 2024-2026 年最新学术研究和业界实践
> 更新日期：2026-01-16

## 1. 核心问题：为什么简单滑动窗口不够好？

简单的"保留最近 N 条消息"策略存在以下问题：

| 问题 | 影响 |
|------|------|
| **丢失任务定义** | 前几轮对话中的任务目标、约束条件被丢弃，导致 Agent 偏离原始意图 |
| **中期信息遗忘** | 重要的决策点、关键事实在中间轮次，被截断后丢失 |
| **Lost-in-the-Middle** | 即使保留了内容，LLM 对中间位置的注意力也较弱 |
| **代码任务特殊性** | 代码修改的上下文依赖复杂，错过早期文件结构、需求定义会导致严重错误 |

## 2. 最新学术研究（2025-2026）

### 2.1 SimpleMem: 高效终身记忆（2026年1月）

**论文**: *SimpleMem: Efficient Lifelong Memory for LLM Agents*

**核心方法**：
```
┌─────────────────────────────────────────────────────────────────┐
│                    SimpleMem 三阶段 Pipeline                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 语义结构压缩 (Semantic Structured Compression)              │
│     - 将对话按语义结构分块                                       │
│     - 保留关键实体和关系                                         │
│                                                                  │
│  2. 递归记忆整合 (Recursive Memory Consolidation)               │
│     - 周期性合并相似记忆                                         │
│     - 去除冗余信息                                               │
│                                                                  │
│  3. 自适应查询感知检索 (Adaptive Query-Aware Retrieval)         │
│     - 根据当前查询动态选择相关记忆                               │
│     - 结合语义相似度和重要性评分                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**效果**: Token 消耗减少 **30 倍**，F1 提升数个百分点。

### 2.2 Active Context Compression（2026年1月）

**论文**: *Active Context Compression: Autonomous Memory Management in LLM Agents*

**核心思想**: Agent 自主决定何时压缩、何时保留

```python
# Focus Agent 自主记忆管理
class FocusAgent:
    def decide_action(self, context, task):
        if self.should_compress(context):
            return "COMPRESS"  # 压缩旧经验到知识块
        elif self.should_prune(context):
            return "PRUNE"     # 裁剪无关历史
        else:
            return "KEEP"      # 保持原样
```

**效果**: Token 减少 **22.7%**（最高 57%），准确率几乎不变。

### 2.3 PAACE: 计划感知压缩（2025年12月）

**论文**: *PAACE: Plan-Aware Automated Agent Context Engineering*

**核心思想**: 根据 Agent 的任务计划结构，智能决定哪些历史与未来步骤相关

```
任务计划:  步骤1 → 步骤2 → 步骤3 → 步骤4
                    ↑
               当前位置

相关性判断:
- 步骤1 的结果 → 与步骤3 高度相关 ✅ 保留
- 步骤1 的过程细节 → 与步骤3 无关 ❌ 压缩
- 步骤2 的全部内容 → 与步骤3 相关 ✅ 保留
```

**效果**: 在 AppWorld、OfficeBench 等长任务上，Token 显著减少，准确率保持。

### 2.4 Chain-of-Agents (CoA)（2024年6月）

**论文**: *Chain-of-Agents: Large Language Models Collaborating on Long-Context Tasks*

**核心方法**: 多 Agent 协作处理长上下文

```
┌─────────────────────────────────────────────────────────────────┐
│                    Chain-of-Agents 架构                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  输入文档/历史 ──→ 语义分块                                      │
│                     │                                            │
│         ┌──────────┼──────────┐                                 │
│         ↓          ↓          ↓                                 │
│     Worker 1   Worker 2   Worker 3   (各自处理短上下文)         │
│         │          │          │                                  │
│         └──────────┼──────────┘                                 │
│                    ↓                                             │
│              Manager Agent   (汇总输出)                          │
│                    │                                             │
│                    ↓                                             │
│               最终回答                                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**效果**: QA、摘要、代码补全任务提升 5-10%，缓解 Lost-in-the-Middle 问题。

### 2.5 SeCom: 对话分段记忆（2025年2月）

**论文**: *On Memory Construction and Retrieval for Personalized Conversational Agents*

**核心方法**: 按主题分割对话，生成 topic-coherent segments

```python
# 对话分段示例
segments = [
    Segment(topic="任务定义", turns=[1, 2, 3]),
    Segment(topic="技术讨论", turns=[4, 5, 6, 7]),
    Segment(topic="方案确认", turns=[8, 9]),
    Segment(topic="实现细节", turns=[10, 11, 12]),
]

# 检索时按主题相关性选择
relevant_segments = retriever.search(
    query="如何实现缓存功能",
    filter=lambda s: s.topic in ["技术讨论", "实现细节"]
)
```

### 2.6 Sculptor: 主动上下文管理（2025年）

**论文**: *Sculptor: Empowering LLMs with Active Context Management*

**核心方法**: 主动分割、隐藏/恢复、智能搜索以减少干扰信息

```
┌─────────────────────────────────────────────────────────────────┐
│                    Sculptor 工具集                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Fragment Summaries - 分段摘要                               │
│     将长上下文拆分为可管理的摘要片段                            │
│                                                                  │
│  2. Hide / Restore - 隐藏与恢复                                 │
│     临时隐藏不相关信息，需要时恢复                              │
│                                                                  │
│  3. Smart Search - 智能过滤                                     │
│     过滤早期上下文中的"噪声"信息                               │
│     减少 Proactive Interference（前摄干扰）                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**效果**: 在信息稀疏任务中显著提升推理质量。

### 2.7 Cognitive Workspace: 认知工作空间（2025年）

**论文**: *Cognitive Workspace: Active Memory Management for LLMs*

**核心思想**: 借鉴认知科学，引入分层工作记忆

```
┌─────────────────────────────────────────────────────────────────┐
│                    认知工作空间架构                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Working Buffers (工作缓冲区)                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  • 任务驱动的上下文优化                                   │  │
│  │  • 分层认知缓存                                           │  │
│  │  • 主动信息策展 (Information Curation)                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Memory Reuse Rate: ~58.6%                                      │
│  Net Efficiency Gain: ~17-18%                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.8 AgeMem: 统一长短期记忆（2026年1月）

**论文**: *AgeMem: Agentic Memory for LLM Agents*

**核心方法**:
- Memory 操作工具化（作为 Agent 的可调用工具）
- 通过 RL/策略决定何时保留、何时删除
- 短期与长期记忆的协同

### 2.9 Locret: KV Cache 驱逐策略（2025年）

**论文**: *Locret: Enhancing Eviction in Long-Context LLM Inference*

**核心方法**:
- 精细粒度的 KV Cache 驱逐策略
- Chunked Prefill 场景下精确删除无关缓存
- 极大减少显存消耗，保持生成质量

## 3. 业界最佳实践

### 3.1 四大动作模式（Write / Select / Compress / Isolate）

这是社区总结的 Agent 上下文工程模板：

| 动作 | 说明 | 实现要点 |
|------|------|----------|
| **Write** | 将临时数据外部化 | 工具 trace、计划、大型输出写入外部存储 |
| **Select** | 动态检索相关内容 | 根据当前 query 检索，而非全量发送 |
| **Compress** | 周期性压缩旧历史 | 摘要、合并、去重 |
| **Isolate** | 任务/角色隔离 | 不同子任务维护独立 memory partition |

### 3.2 混合记忆架构（Hybrid Memory）

```
┌─────────────────────────────────────────────────────────────────┐
│                      混合记忆架构                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  Pinned Memory (固定记忆)                               │     │
│  │  - 系统提示词                                           │     │
│  │  - 任务定义/目标                                        │     │
│  │  - 用户偏好/约束                                        │     │
│  │  永不删除，始终包含在 prompt 中                         │     │
│  └────────────────────────────────────────────────────────┘     │
│                          │                                       │
│                          ▼                                       │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  Summary Memory (摘要记忆)                              │     │
│  │  - 早期对话摘要                                         │     │
│  │  - 关键决策点                                           │     │
│  │  - 工具执行结果摘要                                     │     │
│  │  压缩后保留，按需检索                                   │     │
│  └────────────────────────────────────────────────────────┘     │
│                          │                                       │
│                          ▼                                       │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  Recent Buffer (近期缓冲)                               │     │
│  │  - 最近 M 条完整对话                                    │     │
│  │  - 保持对话连贯性                                       │     │
│  │  滑动窗口，超出后压缩到 Summary                         │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 代码任务特殊处理

对于代码生成/修改任务，需要特殊的上下文管理：

| 内容类型 | 保留策略 | 原因 |
|----------|----------|------|
| **文件结构** | Pinned | 代码修改依赖目录结构理解 |
| **需求定义** | Pinned | 功能实现必须符合原始需求 |
| **已修改文件列表** | Summary | 避免重复修改或遗漏 |
| **错误/测试结果** | Recent | 用于调试和迭代 |
| **中间代码片段** | Compress | 只保留最终版本 |

### 3.4 Observation Masking（观察屏蔽）

**论文**: *The Complexity Trap: Simple Observation Masking Is as Efficient as LLM Summarization*

**核心发现**: 简单的屏蔽（不发送某些历史）有时比复杂的摘要更有效

```python
def mask_observations(history, current_task):
    """屏蔽与当前任务无关的观察"""
    masked = []
    for item in history:
        if item.type == "tool_output" and not is_relevant(item, current_task):
            # 屏蔽：只保留元数据，不保留内容
            masked.append(MaskedItem(
                type=item.type,
                tool_name=item.tool_name,
                status="success/failed",
                content="[已屏蔽]"
            ))
        else:
            masked.append(item)
    return masked
```

## 4. 针对代码 Agent 的最佳实践

### 4.1 代码任务的特殊挑战

| 挑战 | 说明 |
|------|------|
| **长依赖链** | 修改 A 文件 → 影响 B 文件 → 需要更新 C 文件 |
| **上下文碎片化** | 代码分散在多个文件，需要同时理解 |
| **迭代修复** | 错误修复可能需要回溯多个步骤 |
| **工具输出庞大** | 文件内容、测试结果可能非常长 |

### 4.2 SWE-Agent / Devin 风格的上下文管理

参考业界领先的代码 Agent，推荐以下策略：

```
┌─────────────────────────────────────────────────────────────────┐
│                 代码 Agent 上下文管理策略                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 任务摘要层 (Task Summary)                                    │
│     ┌─────────────────────────────────────────────────────────┐ │
│     │ 目标: 实现用户认证功能                                    │ │
│     │ 约束: 使用 JWT，支持刷新令牌                              │ │
│     │ 已完成: auth/login.py, auth/token.py                     │ │
│     │ 待完成: auth/refresh.py, tests/                          │ │
│     └─────────────────────────────────────────────────────────┘ │
│                                                                  │
│  2. 活跃文件层 (Active Files)                                    │
│     ┌─────────────────────────────────────────────────────────┐ │
│     │ 当前编辑: auth/refresh.py (完整内容)                     │ │
│     │ 相关文件: auth/token.py (关键片段)                       │ │
│     │ 依赖文件: models/user.py (签名摘要)                      │ │
│     └─────────────────────────────────────────────────────────┘ │
│                                                                  │
│  3. 执行历史层 (Execution History)                               │
│     ┌─────────────────────────────────────────────────────────┐ │
│     │ 最近 3 次工具调用:                                        │ │
│     │ - read_file(auth/token.py) ✅                            │ │
│     │ - write_file(auth/refresh.py) ✅                         │ │
│     │ - run_tests() ❌ "2 tests failed"                        │ │
│     │ 早期执行: [摘要] 已读取 5 个文件，修改 2 个文件          │ │
│     └─────────────────────────────────────────────────────────┘ │
│                                                                  │
│  4. 错误追踪层 (Error Tracking)                                  │
│     ┌─────────────────────────────────────────────────────────┐ │
│     │ 当前错误:                                                 │ │
│     │ - test_refresh_token: AssertionError at line 45         │ │
│     │ 已修复错误: [摘要] 3 个类型错误，1 个导入错误            │ │
│     └─────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 代码 Agent 专用压缩策略

```python
class CodeAgentContextManager:
    """代码 Agent 专用上下文管理器"""

    def __init__(self):
        # 固定记忆（不压缩）
        self.pinned = {
            "task_definition": None,      # 任务定义
            "constraints": [],            # 约束条件
            "file_structure": None,       # 项目结构
        }

        # 活跃文件（动态管理）
        self.active_files = LRUCache(maxsize=5)  # 最多 5 个活跃文件

        # 执行历史（压缩管理）
        self.execution_history = {
            "recent": deque(maxlen=5),    # 最近 5 次执行
            "summary": "",                 # 早期执行摘要
        }

        # 错误追踪
        self.errors = {
            "current": [],                 # 当前错误
            "fixed_summary": "",           # 已修复错误摘要
        }

    def add_file_content(self, path: str, content: str, relevance: str):
        """添加文件内容，根据相关性决定保留策略"""
        if relevance == "editing":
            # 正在编辑：保留完整内容
            self.active_files[path] = {"content": content, "type": "full"}
        elif relevance == "related":
            # 相关文件：保留关键片段
            self.active_files[path] = {
                "content": self._extract_key_parts(content),
                "type": "partial"
            }
        elif relevance == "dependency":
            # 依赖文件：只保留签名
            self.active_files[path] = {
                "content": self._extract_signatures(content),
                "type": "signature"
            }

    def add_tool_execution(self, tool: str, result: str, success: bool):
        """添加工具执行结果"""
        execution = {
            "tool": tool,
            "result": result[:500] if success else result,  # 失败保留完整错误
            "success": success,
        }
        self.execution_history["recent"].append(execution)

        # 如果历史过长，压缩到摘要
        if len(self.execution_history["recent"]) >= 5:
            self._compress_execution_history()

    def _compress_execution_history(self):
        """压缩执行历史"""
        old = list(self.execution_history["recent"])[:-3]  # 保留最近 3 条
        summary = f"已执行 {len(old)} 次工具调用: "
        summary += ", ".join([
            f"{e['tool']}({'✅' if e['success'] else '❌'})"
            for e in old
        ])
        self.execution_history["summary"] = summary
        # 清理旧记录
        self.execution_history["recent"] = deque(
            list(self.execution_history["recent"])[-3:],
            maxlen=5
        )
```

## 5. 推荐实现方案

### 5.1 核心组件

基于最新研究，推荐以下核心组件：

| 组件 | 功能 | 触发条件 |
|------|------|----------|
| **KeyDetector** | 识别关键消息（任务定义、决策点） | 每条消息 |
| **PlanTracker** | 跟踪任务计划结构 | 计划变更时 |
| **SummaryManager** | 管理摘要生成和更新 | Token 超阈值 / 阶段切换 |
| **RelevanceScorer** | 评估历史与当前任务的相关性 | 构建 prompt 时 |
| **MemoryStore** | 长期记忆存储和检索 | 写入/检索时 |

### 5.2 完整流程

```
用户输入
    │
    ▼
┌─────────────────┐
│  KeyDetector    │──→ 是否关键？──→ 标记为 Pinned
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  PlanTracker    │──→ 计划是否变更？──→ 触发摘要
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ RelevanceScorer │──→ 评估历史相关性
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ SummaryManager  │──→ 需要压缩？──→ 生成摘要
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  构建 Prompt    │──→ Pinned + Summary + Recent + Query
└─────────────────┘
    │
    ▼
调用 LLM
    │
    ▼
┌─────────────────┐
│  MemoryStore    │──→ 存储重要结果
└─────────────────┘
```

### 5.3 配置参数建议

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `recent_buffer_size` | 5-10 条 | 保留最近消息数 |
| `summary_token_limit` | 500-1000 | 摘要最大 Token |
| `compression_threshold` | 0.7 | 达到预算 70% 时触发压缩 |
| `relevance_top_k` | 5-10 | 检索相关记忆条数 |
| `pinned_types` | ["task_definition", "constraints", "user_preference"] | 固定记忆类型 |
| `code_active_files` | 5 | 代码任务活跃文件数 |

## 6. 效果评估指标

### 6.1 量化指标

| 指标 | 计算方式 | 目标 |
|------|----------|------|
| **Token 节省率** | `(原始 - 压缩后) / 原始` | > 50% |
| **任务成功率** | 成功完成的任务数 / 总任务数 | ≥ 原方案 |
| **上下文完整性** | 关键信息保留率 | > 90% |
| **缓存命中率** | 缓存 Token / 总 Token | > 30% |
| **压缩延迟** | 压缩操作耗时 | < 500ms |

### 6.2 定性评估

- 任务定义是否在长对话后仍被正确理解？
- 早期决策是否影响后续行为？
- 代码修改是否保持一致性？
- 错误修复是否正确回溯？

## 7. 与当前系统的集成建议

### 7.1 优先级排序

| 优先级 | 改进项 | 预期收益 | 实现复杂度 |
|--------|--------|----------|------------|
| **P0** | 关键消息检测 + Pinned Memory | 保留任务定义 | 低 |
| **P0** | 摘要自动触发 | 压缩中期历史 | 中 |
| **P1** | 计划感知压缩 | 智能选择保留内容 | 中 |
| **P1** | 代码任务专用管理 | 提升代码任务质量 | 中 |
| **P2** | 多 Agent 协作（CoA） | 处理超长任务 | 高 |
| **P2** | 自主记忆管理（Focus Agent） | 最优 Token 利用 | 高 |

### 7.2 实施路线图

```
Phase 1 (2周)
├── 实现 KeyDetector（关键消息检测）
├── 实现 Pinned Memory（固定记忆）
└── 集成到现有 SmartContextCompressor

Phase 2 (2周)
├── 实现 PlanTracker（计划追踪）
├── 优化摘要触发策略
└── 添加代码任务专用处理

Phase 3 (3周)
├── 实现 RelevanceScorer（相关性评分）
├── 优化长期记忆检索
└── 添加监控和评估指标

Phase 4 (持续)
├── 根据评估结果调优参数
├── 探索 Multi-Agent 方案
└── 研究自主记忆管理
```

## 8. 参考资源

### 论文

1. SimpleMem (2026) - Efficient Lifelong Memory for LLM Agents
2. Active Context Compression (2026) - Autonomous Memory Management
3. PAACE (2025) - Plan-Aware Automated Agent Context Engineering
4. Chain-of-Agents (2024) - LLMs Collaborating on Long-Context Tasks
5. SeCom (2025) - Memory Construction and Retrieval for Conversational Agents
6. FoldAct (2025) - Efficient and Stable Context Folding
7. Compactor (2025) - KV Cache Compression via Leverage Score Sampling

### 开源实现

- LangChain: ConversationSummaryBufferMemory
- LlamaIndex: ContextCompressor
- OpenAI Agents SDK: Session Memory

### 社区讨论

- Reddit r/ContextEngineering: Modern LLM Context Engineering Patterns
- Reddit r/LocalLLaMA: Context Window Management Strategies
