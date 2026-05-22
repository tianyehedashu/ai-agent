# LiteLLM 支持的中国主流 LLM 模型列表

> 更新时间: 2026-01-17
> LiteLLM 版本: v1.80.16
> 测试环境: 基于项目配置的 API Key 实际测试

## 概述

本文档列出了通过 LiteLLM 可直接调用的中国主流 LLM 提供商模型，包括 DeepSeek、阿里云 DashScope（通义千问）、智谱AI（GLM）、火山引擎（豆包）。

### 测试统计

| 提供商 | 可用模型数 | 成功率 | 平均延迟 |
|--------|-----------|--------|----------|
| DeepSeek | 3 | 100% | 2595ms |
| DashScope | 17 | 89% | 1341ms |
| 智谱AI | 6 | 33%* | 1622ms |
| 火山引擎 | 1+ | 100% | 3361ms |

> *智谱AI 大部分模型因并发测试触发限流，实际模型可用

---

## 一、DeepSeek (深度求索)

### 环境配置

```bash
export DEEPSEEK_API_KEY=sk-xxx
```

### API 信息

- **API Base**: `https://api.deepseek.com`
- **LiteLLM 前缀**: `deepseek/`
- **文档**: https://platform.deepseek.com/api-docs

### 可用模型

| 模型名 | LiteLLM 调用方式 | 延迟 | 参数规模 | 上下文 | 工具调用 | 说明 |
|--------|-----------------|------|----------|--------|---------|------|
| DeepSeek Chat (V3) | `deepseek/deepseek-chat` | 1809ms | 671B MoE (37B激活) | 64K | ✅ | 主力对话模型 |
| DeepSeek Coder | `deepseek/deepseek-coder` | 1859ms | 33B | 16K | ✅ | 代码生成专用 |
| DeepSeek Reasoner (R1) | `deepseek/deepseek-reasoner` | 4116ms | 671B MoE (37B激活) | 64K | ❌ | 推理模型，支持 reasoning_content |

### 价格 (2026-01)

| 模型 | 输入价格 | 输出价格 | 缓存命中 |
|------|---------|---------|---------|
| deepseek-chat | ¥1/百万tokens | ¥2/百万tokens | ¥0.1/百万tokens |
| deepseek-reasoner | ¥4/百万tokens | ¥16/百万tokens | ¥0.4/百万tokens |

### 调用示例

```python
from litellm import completion

response = completion(
    model="deepseek/deepseek-chat",
    messages=[{"role": "user", "content": "你好"}],
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    temperature=0.7,
    max_tokens=4096
)
```

### 注意事项

- DeepSeek 官方 API **只提供 3 个主力模型**
- R1 蒸馏版 (Distill) 需要通过第三方平台访问:
  - TogetherAI: `together/deepseek-r1-distill-llama-70b`
  - Fireworks: `fireworks/deepseek-r1-distill-qwen-32b`
- `deepseek-reasoner` 返回 `reasoning_content` 字段包含思维过程

---

## 二、阿里云 DashScope (通义千问)

### 环境配置

```bash
export DASHSCOPE_API_KEY=sk-xxx
```

### API 信息

- **API Base**: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- **LiteLLM 前缀**: `dashscope/`
- **文档**: https://help.aliyun.com/zh/dashscope/

### 可用模型

#### 商业版

| 模型名 | LiteLLM 调用方式 | 延迟 | 上下文 | 工具调用 | 说明 |
|--------|-----------------|------|--------|---------|------|
| 通义千问 Turbo | `dashscope/qwen-turbo` | 407ms | 128K | ✅ | 速度最快 |
| 通义千问 Turbo (最新) | `dashscope/qwen-turbo-latest` | 559ms | 128K | ✅ | 最新版本 |
| 通义千问 Plus | `dashscope/qwen-plus` | 1438ms | 128K | ✅ | 平衡版 |
| 通义千问 Plus (最新) | `dashscope/qwen-plus-latest` | 1689ms | 128K | ✅ | 最新版本 |
| 通义千问 Max | `dashscope/qwen-max` | 712ms | 32K | ✅ | 能力最强 |
| 通义千问 Max (最新) | `dashscope/qwen-max-latest` | 1562ms | 32K | ✅ | 最新版本 |

#### 视觉模型

| 模型名 | LiteLLM 调用方式 | 延迟 | 上下文 | 工具调用 | 说明 |
|--------|-----------------|------|--------|---------|------|
| 通义千问 VL Plus | `dashscope/qwen-vl-plus` | 781ms | 32K | ❌ | 视觉理解 |
| 通义千问 VL Max | `dashscope/qwen-vl-max` | 955ms | 32K | ✅ | 视觉理解增强 |

#### Qwen 2.5 开源版

| 模型名 | LiteLLM 调用方式 | 延迟 | 参数 | 上下文 | 说明 |
|--------|-----------------|------|------|--------|------|
| Qwen 2.5 72B | `dashscope/qwen2.5-72b-instruct` | 1527ms | 72B | 128K | 开源最强 |
| Qwen 2.5 32B | `dashscope/qwen2.5-32b-instruct` | 921ms | 32B | 128K | 平衡版 |
| Qwen 2.5 14B | `dashscope/qwen2.5-14b-instruct` | 734ms | 14B | 128K | 轻量版 |
| Qwen 2.5 7B | `dashscope/qwen2.5-7b-instruct` | 1112ms | 7B | 128K | 最轻量 |

#### Qwen 2.5 代码专用

| 模型名 | LiteLLM 调用方式 | 延迟 | 参数 | 说明 |
|--------|-----------------|------|------|------|
| Qwen 2.5 Coder 32B | `dashscope/qwen2.5-coder-32b-instruct` | 446ms | 32B | 代码最强 |
| Qwen 2.5 Coder 14B | `dashscope/qwen2.5-coder-14b-instruct` | 1058ms | 14B | 代码平衡 |
| Qwen 2.5 Coder 7B | `dashscope/qwen2.5-coder-7b-instruct` | 909ms | 7B | 代码轻量 |

#### 推理模型

| 模型名 | LiteLLM 调用方式 | 延迟 | 参数 | 说明 |
|--------|-----------------|------|------|------|
| QwQ 32B Preview | `dashscope/qwq-32b-preview` | 1622ms | 32B | 推理增强，类似 o1/R1 |
| Qwen3 235B-A22B | `dashscope/qwen3-235b-a22b` | 8263ms | 235B (22B激活) | MoE 旗舰 |

### 价格参考

| 模型 | 输入价格 (¥/千tokens) | 输出价格 (¥/千tokens) |
|------|---------------------|---------------------|
| qwen-turbo | 0.002 | 0.006 |
| qwen-plus | 0.004 | 0.012 |
| qwen-max | 0.02 | 0.06 |
| qwen2.5-72b | 0.004 | 0.012 |
| qwen2.5-coder-32b | 0.002 | 0.006 |

---

## 三、智谱AI (GLM 系列)

### 环境配置

```bash
export ZHIPUAI_API_KEY=xxx
```

### API 信息

- **API Base**: `https://open.bigmodel.cn/api/paas/v4`
- **LiteLLM 前缀**: `zai/`
- **文档**: https://open.bigmodel.cn/dev/api

### 可用模型

| 模型名 | LiteLLM 调用方式 | 延迟 | 上下文 | 工具调用 | 说明 |
|--------|-----------------|------|--------|---------|------|
| GLM-4 Flash | `zai/glm-4-flash` | 661ms | 128K | ✅ | 极速响应，免费 |
| GLM-4V Flash | `zai/glm-4v-flash` | 642ms | 8K | ❌ | 视觉快速版 |
| GLM-4.5 Air | `zai/glm-4.5-air` | 1831ms | 128K | ✅ | 高性价比 |
| GLM-4.5 Flash | `zai/glm-4.5-flash` | 2388ms | 128K | ✅ | 4.5 快速版 |
| GLM-4.6 | `zai/glm-4.6` | 2143ms | 200K | ✅ | 最新稳定版 |
| GLM-4.6V | `zai/glm-4.6v` | 2065ms | 128K | ✅ | 视觉理解 |

### 其他支持的模型 (需降低并发避免限流)

| 模型名 | LiteLLM 调用方式 | 上下文 | 说明 |
|--------|-----------------|--------|------|
| GLM-4.7 (最新旗舰) | `zai/glm-4-alltools` | 200K | 355B MoE，支持 Agent |
| GLM-4 | `zai/glm-4` | 128K | 主力稳定版 |
| GLM-4 Plus | `zai/glm-4-plus` | 128K | 增强版 |
| GLM-4 Air | `zai/glm-4-air` | 128K | 轻量版 |
| GLM-4 Long | `zai/glm-4-long` | 1M | 超长上下文 |
| CodeGeeX-4 | `zai/codegeex-4` | 128K | 代码专用，免费 |

### 价格参考

| 模型 | 输入价格 (¥/千tokens) | 输出价格 (¥/千tokens) |
|------|---------------------|---------------------|
| glm-4-flash | 0.0001 | 0.0001 |
| glm-4-air | 0.001 | 0.001 |
| glm-4.6 | 0.05 | 0.05 |
| glm-4.7 | 0.05 | 0.05 |

---

## 四、火山引擎 (豆包)

### 环境配置

```bash
export VOLCENGINE_API_KEY=xxx
export VOLCENGINE_CHAT_ENDPOINT_ID=ep-xxx  # 在控制台创建
```

### API 信息

- **API Base**: `https://ark.cn-beijing.volces.com/api/v3`
- **LiteLLM 前缀**: `volcengine/`
- **文档**: https://www.volcengine.com/docs/82379

### 调用方式

火山引擎 **按 Endpoint ID 调用**，不是按模型名。需要先在火山引擎控制台为每个模型创建 Endpoint。

```python
from litellm import completion

response = completion(
    model="volcengine/<your_endpoint_id>",
    messages=[{"role": "user", "content": "你好"}],
    api_key=os.getenv("VOLCENGINE_API_KEY"),
)
```

### 支持的豆包模型系列

在火山引擎控制台创建对应 Endpoint 后可调用:

#### Doubao 1.5 Pro 系列 (高性能)

| 模型 | 上下文 | 价格 (¥/千tokens) | 说明 |
|------|--------|------------------|------|
| doubao-1.5-pro-32k | 32K | 0.0008/0.002 | 专业版 |
| doubao-1.5-pro-128k | 128K | 0.005/0.009 | 长上下文 |
| doubao-1.5-pro-256k | 256K | 0.005/0.009 | 超长上下文 |

#### Doubao 1.5 Lite 系列 (轻量高效)

| 模型 | 上下文 | 价格 (¥/千tokens) | 说明 |
|------|--------|------------------|------|
| doubao-1.5-lite-32k | 32K | 0.0003/0.0006 | 速度快 |
| doubao-1.5-lite-128k | 128K | 0.0008/0.001 | 长上下文 |

#### Doubao Seed 1.6 系列 (最新旗舰)

| 模型 | 上下文 | 说明 |
|------|--------|------|
| doubao-seed-1.6 | 32K | 综合能力最强 |
| doubao-seed-1.6-flash | 32K | 延迟更低 |
| doubao-seed-1.6-vision | 32K | 支持图像 |

#### 其他系列

| 模型 | 说明 |
|------|------|
| doubao-1.5-vision-pro | 视觉理解 |
| doubao-1.5-vision-lite | 视觉轻量版 |
| doubao-thinking-pro | 深度思考 (类似 o1) |
| doubao-character-pro-32k | 角色扮演 |

---

## 快速参考

### 性能排行 (响应延迟 Top 10)

1. 🥇 `dashscope/qwen-turbo` - 407ms
2. 🥈 `dashscope/qwen2.5-coder-32b-instruct` - 446ms
3. 🥉 `dashscope/qwen-turbo-latest` - 559ms
4. `zai/glm-4v-flash` - 642ms
5. `zai/glm-4-flash` - 661ms
6. `dashscope/qwen-max` - 712ms
7. `dashscope/qwen2.5-14b-instruct` - 734ms
8. `dashscope/qwen-vl-plus` - 781ms
9. `dashscope/qwen2.5-coder-7b-instruct` - 909ms
10. `dashscope/qwen2.5-32b-instruct` - 921ms

### 推荐使用场景

| 场景 | 推荐模型 | 理由 |
|------|---------|------|
| 日常对话 | `dashscope/qwen-turbo` | 速度快、成本低 |
| 代码生成 | `dashscope/qwen2.5-coder-32b-instruct` | 代码能力强、响应快 |
| 复杂推理 | `deepseek/deepseek-reasoner` | 思维链输出 |
| 长文档处理 | `zai/glm-4-long` | 100万 token 上下文 |
| 图像理解 | `dashscope/qwen-vl-max` | 视觉能力强 |
| 免费试用 | `zai/glm-4-flash` | 基本免费 |

---

## 测试脚本

项目提供了批量测试脚本，用于验证模型可用性:

```bash
cd backend
uv run python scripts/test_litellm_models.py --check-keys  # 检查 API Key
uv run python scripts/test_litellm_models.py              # 运行测试
uv run python scripts/test_litellm_models.py -p deepseek  # 只测试 DeepSeek
```

详细配置参见: `backend/config/litellm_models.yaml`
