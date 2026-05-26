/**
 * 调用指南 · 按能力分块的示例代码（OpenAI / Anthropic 双风格）
 */

import {
  PLAYGROUND_EXAMPLE_IMAGE_URL,
  PLAYGROUND_EXAMPLE_PROMPTS,
} from '@/features/gateway-playground/playground-example-content'

export interface FlavorCodeTriple {
  curl: string
  ts: string
  py: string
}

export interface CapabilityGuideModule {
  id: string
  title: string
  description: string
  openai: FlavorCodeTriple
  anthropic: FlavorCodeTriple
}

export function buildCapabilityModules(
  baseUrl: string,
  key: string,
  model: string
): CapabilityGuideModule[] {
  const authOpenai = `Authorization: Bearer ${key}`
  const visionPrompt = PLAYGROUND_EXAMPLE_PROMPTS.vision
  const visionImageUrl = PLAYGROUND_EXAMPLE_IMAGE_URL

  return [
    {
      id: 'tools',
      title: '工具调用（Tools）',
      description: '适合需要实时数据、业务系统查询或函数执行的模型。',
      openai: {
        curl: `curl "${baseUrl}/chat/completions" \\
  -H "Content-Type: application/json" \\
  -H "${authOpenai}" \\
  -d '{
    "model": "${model}",
    "messages": [{"role": "user", "content": "查询北京今天的天气，并说明是否适合户外跑步。"}],
    "tools": [{
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "查询指定城市的实时天气",
        "parameters": {
          "type": "object",
          "properties": {"city": {"type": "string"}},
          "required": ["city"]
        }
      }
    }],
    "tool_choice": "auto"
  }'`,
        ts: `const completion = await client.chat.completions.create({
  model: "${model}",
  messages: [{ role: "user", content: "查询北京今天的天气，并说明是否适合户外跑步。" }],
  tools: [{
    type: "function",
    function: {
      name: "get_weather",
      description: "查询指定城市的实时天气",
      parameters: {
        type: "object",
        properties: { city: { type: "string" } },
        required: ["city"],
      },
    },
  }],
  tool_choice: "auto",
});`,
        py: `completion = client.chat.completions.create(
    model="${model}",
    messages=[{"role": "user", "content": "查询北京今天的天气，并说明是否适合户外跑步。"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的实时天气",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }],
    tool_choice="auto",
)`,
      },
      anthropic: {
        curl: `curl "${baseUrl}/messages" \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: ${key}" \\
  -H "anthropic-version: 2023-06-01" \\
  -d '{
    "model": "${model}",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "查询北京今天的天气，并说明是否适合户外跑步。"}],
    "tools": [{
      "name": "get_weather",
      "description": "查询指定城市的实时天气",
      "input_schema": {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"]
      }
    }],
    "tool_choice": {"type": "auto"}
  }'`,
        ts: `const message = await client.messages.create({
  model: "${model}",
  max_tokens: 1024,
  messages: [{ role: "user", content: "查询北京今天的天气，并说明是否适合户外跑步。" }],
  tools: [{
    name: "get_weather",
    description: "查询指定城市的实时天气",
    input_schema: {
      type: "object",
      properties: { city: { type: "string" } },
      required: ["city"],
    },
  }],
  tool_choice: { type: "auto" },
});`,
        py: `message = client.messages.create(
    model="${model}",
    max_tokens=1024,
    messages=[{"role": "user", "content": "查询北京今天的天气，并说明是否适合户外跑步。"}],
    tools=[{
        "name": "get_weather",
        "description": "查询指定城市的实时天气",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    }],
    tool_choice={"type": "auto"},
)`,
      },
    },
    {
      id: 'vision',
      title: '视觉理解（图片输入）',
      description: '适合图片理解、结构化提取、质检和风险识别。',
      openai: {
        curl: `curl "${baseUrl}/chat/completions" \\
  -H "Content-Type: application/json" \\
  -H "${authOpenai}" \\
  -d '{
    "model": "${model}",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "${visionPrompt}"},
        {"type": "image_url", "image_url": {"url": "${visionImageUrl}"}}
      ]
    }]
  }'`,
        ts: `await client.chat.completions.create({
  model: "${model}",
  messages: [{
    role: "user",
    content: [
      { type: "text", text: "${visionPrompt}" },
      { type: "image_url", image_url: { url: "${visionImageUrl}" } },
    ],
  }],
});`,
        py: `client.chat.completions.create(
    model="${model}",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "${visionPrompt}"},
            {"type": "image_url", "image_url": {"url": "${visionImageUrl}"}},
        ],
    }],
)`,
      },
      anthropic: {
        curl: `curl "${baseUrl}/messages" \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: ${key}" \\
  -H "anthropic-version: 2023-06-01" \\
  -d '{
    "model": "${model}",
    "max_tokens": 1024,
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "${visionPrompt}"},
        {
          "type": "image",
          "source": {
            "type": "url",
            "url": "${visionImageUrl}"
          }
        }
      ]
    }]
  }'`,
        ts: `await client.messages.create({
  model: "${model}",
  max_tokens: 1024,
  messages: [{
    role: "user",
    content: [
      { type: "text", text: "${visionPrompt}" },
      { type: "image", source: { type: "url", url: "${visionImageUrl}" } },
    ],
  }],
});`,
        py: `client.messages.create(
    model="${model}",
    max_tokens=1024,
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "${visionPrompt}"},
            {"type": "image", "source": {"type": "url", "url": "${visionImageUrl}"}},
        ],
    }],
)`,
      },
    },
    {
      id: 'caching',
      title: 'Prompt Caching',
      description: '适合长系统提示、长文档上下文或多轮复用的固定前缀。',
      openai: {
        curl: `# OpenAI 兼容：视模型/供应商而定，可尝试 extra_headers
curl "${baseUrl}/chat/completions" \\
  -H "Content-Type: application/json" \\
  -H "${authOpenai}" \\
  -d '{
    "model": "${model}",
    "messages": [
      {"role": "system", "content": "你是合同审阅助手。以下长期规则会在多轮审阅中复用..."},
      {"role": "user", "content": "基于这些规则审阅第 12 条，列出风险和修改建议。"}
    ],
    "metadata": {"session_id": "demo-1"}
  }'`,
        ts: `// OpenAI SDK 类型未必含 extra_headers，可用 fetch 或查阅 LiteLLM 透传字段
await fetch("${baseUrl}/chat/completions", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: "Bearer ${key}",
    "anthropic-beta": "prompt-caching-2024-07-31",
  },
  body: JSON.stringify({
    model: "${model}",
    messages: [
      { role: "system", content: "你是合同审阅助手。以下长期规则会在多轮审阅中复用..." },
      { role: "user", content: "基于这些规则审阅第 12 条，列出风险和修改建议。" },
    ],
  }),
});`,
        py: `client.chat.completions.create(
    model="${model}",
    messages=[
        {"role": "system", "content": "你是合同审阅助手。以下长期规则会在多轮审阅中复用..."},
        {"role": "user", "content": "基于这些规则审阅第 12 条，列出风险和修改建议。"},
    ],
    extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
)`,
      },
      anthropic: {
        curl: `curl "${baseUrl}/messages" \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: ${key}" \\
  -H "anthropic-version: 2023-06-01" \\
  -d '{
    "model": "${model}",
    "max_tokens": 1024,
    "system": [{
      "type": "text",
      "text": "你是合同审阅助手。以下长期规则会在多轮审阅中复用...",
      "cache_control": {"type": "ephemeral"}
    }],
    "messages": [{"role": "user", "content": "基于这些规则审阅第 12 条，列出风险和修改建议。"}]
  }'`,
        ts: `await client.messages.create({
  model: "${model}",
  max_tokens: 1024,
  system: [{
    type: "text",
    text: "你是合同审阅助手。以下长期规则会在多轮审阅中复用...",
    cache_control: { type: "ephemeral" },
  }],
  messages: [{ role: "user", content: "基于这些规则审阅第 12 条，列出风险和修改建议。" }],
});`,
        py: `client.messages.create(
    model="${model}",
    max_tokens=1024,
    system=[{
        "type": "text",
        "text": "你是合同审阅助手。以下长期规则会在多轮审阅中复用...",
        "cache_control": {"type": "ephemeral"},
    }],
    messages=[{"role": "user", "content": "基于这些规则审阅第 12 条，列出风险和修改建议。"}],
)`,
      },
    },
    {
      id: 'thinking',
      title: 'Extended Thinking / 深度思考',
      description:
        '仅部分模型支持可分离的思考输出。DashScope Qwen3：extra_body.enable_thinking + 建议 stream；' +
        'DeepSeek Reasoner / QwQ：无需开关，读 reasoning_content；普通对话模型勿传 enable_thinking。',
      openai: {
        curl: `# --- DashScope Qwen3（须 stream + enable_thinking）---
curl -N "${baseUrl}/chat/completions" \\
  -H "Content-Type: application/json" \\
  -H "${authOpenai}" \\
  -d '{
    "model": "${model}",
    "stream": true,
    "messages": [{"role": "user", "content": "为一个月内上线企业 AI 网关制定迁移计划，列出依赖、风险和里程碑。"}],
    "enable_thinking": true
  }'

# 非流式 DashScope 须显式关闭： "enable_thinking": false

# --- DeepSeek Reasoner（内置推理，无需 extra_body）---
# 流式响应 delta 可能含 reasoning_content 与 content`,
        ts: `// DashScope Qwen3：enable_thinking + stream
const stream = await client.chat.completions.create({
  model: "${model}",
  stream: true,
  messages: [{ role: "user", content: "为一个月内上线企业 AI 网关制定迁移计划，列出依赖、风险和里程碑。" }],
  // @ts-expect-error OpenAI SDK 透传
  extra_body: { enable_thinking: true },
});
for await (const chunk of stream) {
  const delta = chunk.choices[0]?.delta;
  if (delta?.reasoning_content) process.stdout.write(delta.reasoning_content);
  if (delta?.content) process.stdout.write(delta.content);
}

// DeepSeek Reasoner：无需 enable_thinking，同样读取 delta.reasoning_content`,
        py: `# DashScope Qwen3（深度思考，须已注册对应别名）
messages = [{"role": "user", "content": "为一个月内上线企业 AI 网关制定迁移计划，列出依赖、风险和里程碑。"}]
stream = client.chat.completions.create(
    model="${model}",
    messages=messages,
    extra_body={"enable_thinking": True},
    stream=True,
)
for chunk in stream:
    delta = chunk.choices[0].delta
    if getattr(delta, "reasoning_content", None):
        print(delta.reasoning_content, end="", flush=True)
    if delta.content:
        print(delta.content, end="", flush=True)

# 非流式：extra_body={"enable_thinking": False}  # DashScope 要求显式关闭`,
      },
      anthropic: {
        curl: `curl "${baseUrl}/messages" \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: ${key}" \\
  -H "anthropic-version: 2023-06-01" \\
  -d '{
    "model": "${model}",
    "max_tokens": 16000,
    "thinking": {"type": "enabled", "budget_tokens": 8000},
    "messages": [{"role": "user", "content": "为一个月内上线企业 AI 网关制定迁移计划，列出依赖、风险和里程碑。"}]
  }'`,
        ts: `await client.messages.create({
  model: "${model}",
  max_tokens: 16000,
  thinking: { type: "enabled", budget_tokens: 8000 },
  messages: [{ role: "user", content: "为一个月内上线企业 AI 网关制定迁移计划，列出依赖、风险和里程碑。" }],
});`,
        py: `client.messages.create(
    model="${model}",
    max_tokens=16000,
    thinking={"type": "enabled", "budget_tokens": 8000},
    messages=[{"role": "user", "content": "为一个月内上线企业 AI 网关制定迁移计划，列出依赖、风险和里程碑。"}],
)`,
      },
    },
    {
      id: 'sse',
      title: '流式事件（SSE）',
      description: '适合长文本、边生成边展示和低首字延迟场景。',
      openai: {
        curl: `curl -N "${baseUrl}/chat/completions" \\
  -H "Content-Type: application/json" \\
  -H "${authOpenai}" \\
  -d '{"model": "${model}", "stream": true, "messages": [{"role": "user", "content": "逐步生成一段 80 字以内的产品发布公告。"}]}'`,
        ts: `const stream = await client.chat.completions.create({
  model: "${model}",
  stream: true,
  messages: [{ role: "user", content: "逐步生成一段 80 字以内的产品发布公告。" }],
});
for await (const chunk of stream) {
  const piece = chunk.choices[0]?.delta?.content;
  if (piece) process.stdout.write(piece);
}`,
        py: `stream = client.chat.completions.create(
    model="${model}",
    stream=True,
    messages=[{"role": "user", "content": "逐步生成一段 80 字以内的产品发布公告。"}],
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="", flush=True)`,
      },
      anthropic: {
        curl: `curl -N "${baseUrl}/messages" \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: ${key}" \\
  -H "anthropic-version: 2023-06-01" \\
  -d '{"model": "${model}", "max_tokens": 1024, "stream": true, "messages": [{"role": "user", "content": "逐步生成一段 80 字以内的产品发布公告。"}]}'`,
        ts: `const stream = client.messages.stream({
  model: "${model}",
  max_tokens: 1024,
  messages: [{ role: "user", content: "逐步生成一段 80 字以内的产品发布公告。" }],
});
for await (const event of stream) {
  if (event.type === "content_block_delta" && event.delta.type === "text_delta") {
    process.stdout.write(event.delta.text);
  }
}`,
        py: `with client.messages.stream(
    model="${model}",
    max_tokens=1024,
    messages=[{"role": "user", "content": "逐步生成一段 80 字以内的产品发布公告。"}],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)`,
      },
    },
    {
      id: 'metadata',
      title: 'metadata 与常用参数',
      description: '适合演示温度、停止词、追踪 ID 等可观测参数。',
      openai: {
        curl: `curl "${baseUrl}/chat/completions" \\
  -H "Content-Type: application/json" \\
  -H "${authOpenai}" \\
  -d '{
    "model": "${model}",
    "temperature": 0.7,
    "max_tokens": 512,
    "stop": ["###"],
    "metadata": {"trace_id": "req-001", "env": "prod"},
    "messages": [{"role": "user", "content": "用三句话总结本次请求的处理策略。"}]
  }'`,
        ts: `await client.chat.completions.create({
  model: "${model}",
  temperature: 0.7,
  max_tokens: 512,
  stop: ["###"],
  metadata: { trace_id: "req-001", env: "prod" },
  messages: [{ role: "user", content: "用三句话总结本次请求的处理策略。" }],
});`,
        py: `client.chat.completions.create(
    model="${model}",
    temperature=0.7,
    max_tokens=512,
    stop=["###"],
    metadata={"trace_id": "req-001", "env": "prod"},
    messages=[{"role": "user", "content": "用三句话总结本次请求的处理策略。"}],
)`,
      },
      anthropic: {
        curl: `curl "${baseUrl}/messages" \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: ${key}" \\
  -H "anthropic-version: 2023-06-01" \\
  -d '{
    "model": "${model}",
    "max_tokens": 1024,
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 40,
    "stop_sequences": ["###"],
    "metadata": {"trace_id": "req-001"},
    "messages": [{"role": "user", "content": "用三句话总结本次请求的处理策略。"}]
  }'`,
        ts: `await client.messages.create({
  model: "${model}",
  max_tokens: 1024,
  temperature: 0.7,
  top_p: 0.9,
  top_k: 40,
  stop_sequences: ["###"],
  metadata: { trace_id: "req-001" },
  messages: [{ role: "user", content: "用三句话总结本次请求的处理策略。" }],
});`,
        py: `client.messages.create(
    model="${model}",
    max_tokens=1024,
    temperature=0.7,
    top_p=0.9,
    top_k=40,
    stop_sequences=["###"],
    metadata={"trace_id": "req-001"},
    messages=[{"role": "user", "content": "用三句话总结本次请求的处理策略。"}],
)`,
      },
    },
    {
      id: 'errors',
      title: '错误响应（Errors）',
      description:
        '业务错误（限流、预算、模型白名单等）映射为 Anthropic `error.type`；HTTP 状态与 OpenAI 兼容面一致（如 429 / 402）。',
      openai: {
        curl: `curl "${baseUrl}/chat/completions" \\
  -H "Content-Type: application/json" \\
  -H "${authOpenai}" \\
  -d '{"model": "${model}", "messages": [{"role": "user", "content": "发送一个最小测试请求，用于验证错误处理和日志链路。"}]}'`,
        ts: `// 429: error.type === "rate_limit_exceeded"
// 402: error.type === "budget_exceeded"
try {
  await client.chat.completions.create({ model: "${model}", messages: [...] });
} catch (e) {
  console.error(e.status, e.error?.type, e.error?.message);
}`,
        py: `# 429: error["type"] == "rate_limit_exceeded"
# 402: error["type"] == "budget_exceeded"
try:
    client.chat.completions.create(model="${model}", messages=[...])
except Exception as e:
    print(getattr(e, "status_code", None), e)`,
      },
      anthropic: {
        curl: `# 429 示例（限流）
# {"type":"error","error":{"type":"rate_limit_error","message":"..."}}
curl -i "${baseUrl}/messages" \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: ${key}" \\
  -H "anthropic-version: 2023-06-01" \\
  -d '{"model": "${model}", "max_tokens": 32, "messages": [{"role": "user", "content": "发送一个最小测试请求，用于验证错误处理和日志链路。"}]}'`,
        ts: `// 429: detail.error.type === "rate_limit_error"
// 402: detail.error.type === "api_error"（预算用尽）
try {
  await client.messages.create({
    model: "${model}",
    max_tokens: 32,
    messages: [{ role: "user", content: "发送一个最小测试请求，用于验证错误处理和日志链路。" }],
  });
} catch (e) {
  console.error(e.status, e.error?.type);
}`,
        py: `# 429: error["type"] == "rate_limit_error"
# 402: error["type"] == "api_error"
try:
    client.messages.create(
        model="${model}",
        max_tokens=32,
        messages=[{"role": "user", "content": "发送一个最小测试请求，用于验证错误处理和日志链路。"}],
    )
except Exception as e:
    print(getattr(e, "status_code", None), e)`,
      },
    },
  ]
}
