# LLM Gateway 架构设计说明

## 一、LiteLLM 的作用

### 1.1 为什么使用 LiteLLM？

LiteLLM 是一个**统一的多模型接口库**，它的核心价值在于：

```
┌─────────────────────────────────────────────────────────┐
│                    LiteLLM 的作用                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  统一接口：一个 API 调用 100+ 个 LLM 提供商              │
│  ├─ OpenAI (GPT-4, GPT-3.5)                           │
│  ├─ Anthropic (Claude)                                 │
│  ├─ 阿里云 DashScope (通义千问)                         │
│  ├─ DeepSeek                                           │
│  ├─ 火山引擎 (豆包)                                     │
│  ├─ 智谱AI (GLM)                                       │
│  └─ ... 100+ 个提供商                                   │
│                                                         │
│  统一格式：所有模型都使用 OpenAI 兼容的格式              │
│  ├─ messages: [{"role": "user", "content": "..."}]    │
│  ├─ tools: [...]                                       │
│  └─ response: {choices: [{message: {...}}]}            │
│                                                         │
│  自动路由：根据模型名称自动选择正确的 API                │
│  ├─ "gpt-4" → OpenAI API                               │
│  ├─ "claude-3" → Anthropic API                        │
│  ├─ "qwen-turbo" → DashScope API                      │
│  └─ "glm-4" → 智谱AI API                              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 1.2 不使用 LiteLLM 的问题

如果直接使用各个提供商的 SDK：

```python
# ❌ 不好的方式：需要为每个提供商写不同的代码
if model.startswith("gpt-"):
    from openai import OpenAI
    client = OpenAI(api_key=...)
    response = client.chat.completions.create(...)
elif model.startswith("claude-"):
    from anthropic import Anthropic
    client = Anthropic(api_key=...)
    response = client.messages.create(...)
elif model.startswith("qwen-"):
    from dashscope import Generation
    response = Generation.call(...)
# ... 需要为每个提供商写不同的代码
```

**问题：**
- 代码重复：每个提供商都有不同的 API 格式
- 难以维护：添加新模型需要修改多处代码
- 难以切换：切换模型需要重写逻辑

### 1.3 使用 LiteLLM 的优势

```python
# ✅ 好的方式：统一接口
from litellm import acompletion

response = await acompletion(
    model="gpt-4",  # 或 "claude-3" 或 "qwen-turbo" 或 "glm-4"
    messages=[{"role": "user", "content": "Hello"}],
    api_key=...,
)
# 所有模型都使用相同的接口！
```

**优势：**
- 统一接口：所有模型使用相同的 API
- 易于切换：只需改变模型名称
- 易于扩展：添加新模型无需修改代码

---

## 二、Gateway 层的作用

### 2.1 Gateway 层的设计目的

虽然 LiteLLM 提供了统一接口，但**我们还需要一个 Gateway 层**，原因如下：

```
┌─────────────────────────────────────────────────────────┐
│                  Gateway 层的职责                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. 隔离外部依赖                                        │
│     ├─ 将 LiteLLM 的响应转换为内部类型                  │
│     ├─ 避免 LiteLLM 对象污染业务代码                    │
│     └─ 确保类型安全                                     │
│                                                         │
│  2. 统一配置管理                                        │
│     ├─ 管理不同提供商的 API Key                         │
│     ├─ 处理模型名称规范化 (如 "zai/glm-4")              │
│     └─ 统一错误处理                                     │
│                                                         │
│  3. 数据转换和验证                                      │
│     ├─ 将 LiteLLM 响应转换为 LLMResponse               │
│     ├─ 提取工具调用、使用情况等                         │
│     └─ 支持 GLM 的特殊字段 (reasoning_content)          │
│                                                         │
│  4. 业务逻辑封装                                        │
│     ├─ Token 计数                                       │
│     ├─ 重试逻辑                                         │
│     └─ Fallback 机制                                    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 2.2 架构层次

```
┌─────────────────────────────────────────────────────────┐
│                    业务层 (Agent Engine)                 │
│  └─ 使用 LLMResponse / StreamChunk (内部类型)            │
└─────────────────────────────────────────────────────────┘
                        ▲
                        │
┌─────────────────────────────────────────────────────────┐
│                    Gateway 层                            │
│  └─ 转换 LiteLLM 响应 → 内部类型                        │
│  └─ 管理配置、错误处理                                   │
└─────────────────────────────────────────────────────────┘
                        ▲
                        │
┌─────────────────────────────────────────────────────────┐
│                    LiteLLM 层                           │
│  └─ 统一多模型接口                                       │
│  └─ 返回 LiteLLM 对象 (Message, Choices 等)             │
└─────────────────────────────────────────────────────────┘
                        ▲
                        │
┌─────────────────────────────────────────────────────────┐
│                    各提供商 API                          │
│  └─ OpenAI, Anthropic, DashScope, 智谱AI 等             │
└─────────────────────────────────────────────────────────┘
```

### 2.3 Gateway 层的核心功能

#### 功能 1: 模型名称规范化

```python
def _normalize_model_name(self, model: str) -> str:
    """将模型名称转换为 LiteLLM 需要的格式"""
    # "glm-4" → "zai/glm-4" (智谱AI 需要 zai/ 前缀)
    # "qwen-turbo" → "dashscope/qwen-turbo"
    # "gpt-4" → "gpt-4" (OpenAI 不需要前缀)
```

#### 功能 2: API Key 管理

```python
def _get_api_key(self, model: str) -> dict[str, Any]:
    """根据模型名称获取对应的 API Key"""
    # 自动识别模型提供商
    # 返回对应的 API Key 和配置
```

#### 功能 3: 响应转换（核心！）

```python
async def _chat(self, **kwargs) -> LLMResponse:
    """将 LiteLLM 响应转换为内部类型"""
    response = await acompletion(**kwargs)  # LiteLLM 调用

    # 关键：完全隔离 LiteLLM 对象
    # 1. 通过 JSON 序列化/反序列化转换为纯数据
    response_json = json.dumps(response, default=str)
    response_dict = json.loads(response_json)

    # 2. 递归提取基本类型值
    response_dict = self._extract_primitive_value(response_dict)

    # 3. 构造内部类型（不包含任何 LiteLLM 对象）
    return LLMResponse(
        content=...,
        tool_calls=...,
        usage=...,
    )
```

---

## 三、为什么需要 Gateway 层？

### 3.1 问题：LiteLLM 对象污染

**如果不使用 Gateway 层：**

```python
# ❌ 直接使用 LiteLLM 响应
response = await acompletion(...)
# response 是 LiteLLM 的响应对象，包含 Message, Choices 等

# 问题：这些对象会被传递到业务层
event = AgentEvent(
    data={
        "response": response,  # ❌ 包含 LiteLLM 对象！
    }
)
# 当序列化时，Pydantic 会发现类型不匹配，产生警告
```

**使用 Gateway 层：**

```python
# ✅ 通过 Gateway 转换
llm_response = await llm_gateway.chat(...)
# llm_response 是 LLMResponse (内部类型)，只包含基本类型

event = AgentEvent(
    data={
        "response": llm_response.model_dump(),  # ✅ 纯数据，无对象引用
    }
)
# 序列化时不会有问题
```

### 3.2 Gateway 层的隔离作用

```
业务层代码
    ↓
只看到 LLMResponse / StreamChunk (内部类型)
    ↓
Gateway 层
    ↓
处理 LiteLLM 对象 → 转换为内部类型
    ↓
LiteLLM 层
    ↓
调用各提供商 API
```

**好处：**
- 业务层不依赖 LiteLLM
- 可以轻松替换 LiteLLM（如果需要）
- 类型安全，避免序列化问题

---

## 四、当前实现的问题

### 4.1 问题根源

虽然我们使用了 Gateway 层，但 `model_dump()` 可能**没有完全转换嵌套对象**：

```python
# 问题：model_dump() 可能保留嵌套的 LiteLLM 对象
response_dict = response.model_dump()
# response_dict["choices"][0]["message"] 可能仍然是 LiteLLM 的 Message 对象！
```

### 4.2 解决方案

使用 **JSON 序列化/反序列化** + **递归提取**：

```python
# 方法 1: JSON 序列化/反序列化（最彻底）
response_json = json.dumps(response, default=str)
response_dict = json.loads(response_json)
# 所有对象都被转换为基本类型

# 方法 2: 递归提取（双重保障）
response_dict = self._extract_primitive_value(response_dict)
# 确保所有嵌套对象都被转换
```

---

## 五、总结

### LiteLLM 的作用
- **统一接口**：一个 API 调用 100+ 个模型
- **自动路由**：根据模型名称自动选择 API
- **格式统一**：所有模型使用相同的输入/输出格式

### Gateway 层的作用
- **隔离依赖**：将 LiteLLM 对象转换为内部类型
- **配置管理**：统一管理 API Key 和模型配置
- **数据转换**：确保返回的数据不包含外部对象引用
- **业务封装**：提供业务层需要的接口和类型

### 两者的关系
```
LiteLLM: 统一多模型接口（外部库）
    ↓
Gateway: 隔离和转换层（我们的代码）
    ↓
业务层: 使用内部类型（我们的代码）
```

**关键原则：**
- LiteLLM 负责**统一接口**
- Gateway 负责**隔离和转换**
- 业务层**永远不直接接触 LiteLLM 对象**
