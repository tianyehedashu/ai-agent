/**
 * 调用指南 · 按能力分块的示例代码（OpenAI / Anthropic 双风格）
 */

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

  return [
    {
      id: 'tools',
      title: '工具调用（Tools）',
      description:
        'OpenAI 使用 tools + tool_choice；Anthropic 使用 tools + tool_choice，多轮时 assistant 返回 tool_use，user 侧用 tool_result 回传结果。',
      openai: {
        curl: `curl "${baseUrl}/chat/completions" \\
  -H "Content-Type: application/json" \\
  -H "${authOpenai}" \\
  -d '{
    "model": "${model}",
    "messages": [{"role": "user", "content": "北京今天天气？"}],
    "tools": [{
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "查询城市天气",
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
  messages: [{ role: "user", content: "北京今天天气？" }],
  tools: [{
    type: "function",
    function: {
      name: "get_weather",
      description: "查询城市天气",
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
    messages=[{"role": "user", "content": "北京今天天气？"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询城市天气",
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
    "messages": [{"role": "user", "content": "北京今天天气？"}],
    "tools": [{
      "name": "get_weather",
      "description": "查询城市天气",
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
  messages: [{ role: "user", content: "北京今天天气？" }],
  tools: [{
    name: "get_weather",
    description: "查询城市天气",
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
    messages=[{"role": "user", "content": "北京今天天气？"}],
    tools=[{
        "name": "get_weather",
        "description": "查询城市天气",
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
      description:
        'OpenAI 在 messages.content 使用 image_url；Anthropic 使用 image block（base64 或 URL）。需模型支持 vision。',
      openai: {
        curl: `curl "${baseUrl}/chat/completions" \\
  -H "Content-Type: application/json" \\
  -H "${authOpenai}" \\
  -d '{
    "model": "${model}",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "描述这张图"},
        {"type": "image_url", "image_url": {"url": "https://example.com/photo.jpg"}}
      ]
    }]
  }'`,
        ts: `await client.chat.completions.create({
  model: "${model}",
  messages: [{
    role: "user",
    content: [
      { type: "text", text: "描述这张图" },
      { type: "image_url", image_url: { url: "https://example.com/photo.jpg" } },
    ],
  }],
});`,
        py: `client.chat.completions.create(
    model="${model}",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "描述这张图"},
            {"type": "image_url", "image_url": {"url": "https://example.com/photo.jpg"}},
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
        {"type": "text", "text": "描述这张图"},
        {
          "type": "image",
          "source": {
            "type": "url",
            "url": "https://example.com/photo.jpg"
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
      { type: "text", text: "描述这张图" },
      { type: "image", source: { type: "url", url: "https://example.com/photo.jpg" } },
    ],
  }],
});`,
        py: `client.messages.create(
    model="${model}",
    max_tokens=1024,
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "描述这张图"},
            {"type": "image", "source": {"type": "url", "url": "https://example.com/photo.jpg"}},
        ],
    }],
)`,
      },
    },
    {
      id: 'caching',
      title: 'Prompt Caching',
      description:
        'Anthropic 在 system / message 的 text block 上设置 cache_control（ephemeral）。OpenAI 侧取决于上游模型与 LiteLLM 能力，常用 extra_headers 开启 provider 特性。',
      openai: {
        curl: `# OpenAI 兼容：视模型/供应商而定，可尝试 extra_headers
curl "${baseUrl}/chat/completions" \\
  -H "Content-Type: application/json" \\
  -H "${authOpenai}" \\
  -d '{
    "model": "${model}",
    "messages": [
      {"role": "system", "content": "长系统提示..."},
      {"role": "user", "content": "继续对话"}
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
      { role: "system", content: "长系统提示..." },
      { role: "user", content: "继续对话" },
    ],
  }),
});`,
        py: `client.chat.completions.create(
    model="${model}",
    messages=[
        {"role": "system", "content": "长系统提示..."},
        {"role": "user", "content": "继续对话"},
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
      "text": "长系统提示（可缓存）...",
      "cache_control": {"type": "ephemeral"}
    }],
    "messages": [{"role": "user", "content": "继续对话"}]
  }'`,
        ts: `await client.messages.create({
  model: "${model}",
  max_tokens: 1024,
  system: [{
    type: "text",
    text: "长系统提示（可缓存）...",
    cache_control: { type: "ephemeral" },
  }],
  messages: [{ role: "user", content: "继续对话" }],
});`,
        py: `client.messages.create(
    model="${model}",
    max_tokens=1024,
    system=[{
        "type": "text",
        "text": "长系统提示（可缓存）...",
        "cache_control": {"type": "ephemeral"},
    }],
    messages=[{"role": "user", "content": "继续对话"}],
)`,
      },
    },
    {
      id: 'thinking',
      title: 'Extended Thinking',
      description:
        'Anthropic 原生通道支持 thinking 参数；响应 usage 可含推理相关 token。OpenAI 兼容路径取决于具体模型是否支持 reasoning 字段。',
      openai: {
        curl: `# 仅部分推理模型支持（如 o-series）；字段因模型而异
curl "${baseUrl}/chat/completions" \\
  -H "Content-Type: application/json" \\
  -H "${authOpenai}" \\
  -d '{
    "model": "${model}",
    "messages": [{"role": "user", "content": "证明 sqrt(2) 无理"}],
    "max_completion_tokens": 2048
  }'`,
        ts: `// 推理模型示例（字段以模型文档为准）
await client.chat.completions.create({
  model: "${model}",
  messages: [{ role: "user", content: "证明 sqrt(2) 无理" }],
  max_completion_tokens: 2048,
});`,
        py: `client.chat.completions.create(
    model="${model}",
    messages=[{"role": "user", "content": "证明 sqrt(2) 无理"}],
    max_completion_tokens=2048,
)`,
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
    "messages": [{"role": "user", "content": "证明 sqrt(2) 无理"}]
  }'`,
        ts: `await client.messages.create({
  model: "${model}",
  max_tokens: 16000,
  thinking: { type: "enabled", budget_tokens: 8000 },
  messages: [{ role: "user", content: "证明 sqrt(2) 无理" }],
});`,
        py: `client.messages.create(
    model="${model}",
    max_tokens=16000,
    thinking={"type": "enabled", "budget_tokens": 8000},
    messages=[{"role": "user", "content": "证明 sqrt(2) 无理"}],
)`,
      },
    },
    {
      id: 'sse',
      title: '流式事件（SSE）',
      description:
        'OpenAI：data: {...} 行，以 data: [DONE] 结束。Anthropic：event: <name> + data: JSON，以 message_stop 结束。',
      openai: {
        curl: `curl -N "${baseUrl}/chat/completions" \\
  -H "Content-Type: application/json" \\
  -H "${authOpenai}" \\
  -d '{"model": "${model}", "stream": true, "messages": [{"role": "user", "content": "Hi"}]}'`,
        ts: `const stream = await client.chat.completions.create({
  model: "${model}",
  stream: true,
  messages: [{ role: "user", content: "Hi" }],
});
for await (const chunk of stream) {
  const piece = chunk.choices[0]?.delta?.content;
  if (piece) process.stdout.write(piece);
}`,
        py: `stream = client.chat.completions.create(
    model="${model}",
    stream=True,
    messages=[{"role": "user", "content": "Hi"}],
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="", flush=True)`,
      },
      anthropic: {
        curl: `curl -N "${baseUrl}/messages" \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: ${key}" \\
  -H "anthropic-version: 2023-06-01" \\
  -d '{"model": "${model}", "max_tokens": 1024, "stream": true, "messages": [{"role": "user", "content": "Hi"}]}'`,
        ts: `const stream = client.messages.stream({
  model: "${model}",
  max_tokens: 1024,
  messages: [{ role: "user", content: "Hi" }],
});
for await (const event of stream) {
  if (event.type === "content_block_delta" && event.delta.type === "text_delta") {
    process.stdout.write(event.delta.text);
  }
}`,
        py: `with client.messages.stream(
    model="${model}",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hi"}],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)`,
      },
    },
    {
      id: 'metadata',
      title: 'metadata 与常用参数',
      description:
        'metadata 中自定义键会进入网关日志（勿用 gateway_ 前缀）。Anthropic 另支持 top_k、stop_sequences、temperature、top_p 等原生字段。',
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
    "messages": [{"role": "user", "content": "Hello"}]
  }'`,
        ts: `await client.chat.completions.create({
  model: "${model}",
  temperature: 0.7,
  max_tokens: 512,
  stop: ["###"],
  metadata: { trace_id: "req-001", env: "prod" },
  messages: [{ role: "user", content: "Hello" }],
});`,
        py: `client.chat.completions.create(
    model="${model}",
    temperature=0.7,
    max_tokens=512,
    stop=["###"],
    metadata={"trace_id": "req-001", "env": "prod"},
    messages=[{"role": "user", "content": "Hello"}],
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
    "messages": [{"role": "user", "content": "Hello"}]
  }'`,
        ts: `await client.messages.create({
  model: "${model}",
  max_tokens: 1024,
  temperature: 0.7,
  top_p: 0.9,
  top_k: 40,
  stop_sequences: ["###"],
  metadata: { trace_id: "req-001" },
  messages: [{ role: "user", content: "Hello" }],
});`,
        py: `client.messages.create(
    model="${model}",
    max_tokens=1024,
    temperature=0.7,
    top_p=0.9,
    top_k=40,
    stop_sequences=["###"],
    metadata={"trace_id": "req-001"},
    messages=[{"role": "user", "content": "Hello"}],
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
  -d '{"model": "${model}", "messages": [{"role": "user", "content": "Hi"}]}'`,
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
  -d '{"model": "${model}", "max_tokens": 32, "messages": [{"role": "user", "content": "Hi"}]}'`,
        ts: `// 429: detail.error.type === "rate_limit_error"
// 402: detail.error.type === "api_error"（预算用尽）
try {
  await client.messages.create({
    model: "${model}",
    max_tokens: 32,
    messages: [{ role: "user", content: "Hi" }],
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
        messages=[{"role": "user", "content": "Hi"}],
    )
except Exception as e:
    print(getattr(e, "status_code", None), e)`,
      },
    },
  ]
}
