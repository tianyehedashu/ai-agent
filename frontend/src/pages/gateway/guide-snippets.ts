/**
 * Gateway 调用指南 — OpenAI / Anthropic 示例与典型返回片段
 */
export interface FlavorSnippets {
  endpoint: string
  authHeader: string
  curl: string
  curlStream: string
  ts: string
  tsStream: string
  py: string
  pyStream: string
  responseJson: string
  responseSse: string
}

export interface GuideSnippets {
  baseUrl: string
  anthropicBaseUrl: string
  authHeader: string
  modelsCurl: string
  /** multi-grant vkey 时在 modelsCurl 前的注释说明 */
  modelsCurlNote: string | null
  streamHint: string
  openai: FlavorSnippets
  anthropic: FlavorSnippets
}

export interface BuildGuideSnippetsOptions {
  /** 存在跨 team grant 时为 true，用于 models 列表示例注释 */
  multiGrantVkey?: boolean
}

export type ClientIntegrationId = 'claude-code' | 'cursor' | 'openai-sdk' | 'anthropic-sdk'

export interface ClientIntegration {
  id: ClientIntegrationId
  title: string
  summary: string
  blocks: { label: string; code: string }[]
}

export function buildClientIntegrations(
  baseUrl: string,
  key: string,
  model: string,
  snippets: GuideSnippets,
  options?: BuildGuideSnippetsOptions
): ClientIntegration[] {
  const anthropicBase = snippets.anthropicBaseUrl
  const modelIdHint = options?.multiGrantVkey
    ? '模型 id 须与 GET /v1/models 一致（跨工作区带 team-slug/ 前缀）。'
    : '模型名须与网关注册别名一致。'
  return [
    {
      id: 'claude-code',
      title: 'Claude Code',
      summary: '使用 Anthropic Messages 协议；推荐 ANTHROPIC_AUTH_TOKEN。',
      blocks: [
        {
          label: '环境变量',
          code: `export ANTHROPIC_BASE_URL="${anthropicBase}"
export ANTHROPIC_AUTH_TOKEN="${key}"
export ANTHROPIC_MODEL="${model}"
export ANTHROPIC_SMALL_FAST_MODEL="claude-haiku-4-5"`,
        },
        {
          label: '自检',
          code: 'claude --print "ping"',
        },
        {
          label: 'count_tokens',
          code: `curl -s "${anthropicBase}/v1/messages/count_tokens" \\
  -H "x-api-key: ${key}" \\
  -H "anthropic-version: 2023-06-01" \\
  -H "content-type: application/json" \\
  -d '{"model":"claude-haiku-4-5","messages":[{"role":"user","content":"hi"}]}'`,
        },
      ],
    },
    {
      id: 'cursor',
      title: 'Cursor',
      summary: `Settings → Models：Override OpenAI Base URL 与 API Key；${modelIdHint}`,
      blocks: [
        {
          label: '配置步骤',
          code: `1. OpenAI API Key: ${key}
2. Override OpenAI Base URL: ${baseUrl}
3. Add Model: ${model}（${options?.multiGrantVkey ? '与 /v1/models id 一致' : '与 GatewayModel.name 一致'}）
4. 点击 Verify，期望 HTTP 200`,
        },
        {
          label: '验证模型列表',
          code: snippets.modelsCurl,
        },
      ],
    },
    {
      id: 'openai-sdk',
      title: 'OpenAI SDK',
      summary: '与 OpenAI 兼容面一致；baseURL 须包含 /v1。',
      blocks: [
        { label: 'TypeScript', code: snippets.openai.ts },
        { label: 'Python', code: snippets.openai.py },
      ],
    },
    {
      id: 'anthropic-sdk',
      title: 'Anthropic SDK',
      summary: 'baseURL 为服务根（无 /v1 尾段）。',
      blocks: [
        { label: 'TypeScript', code: snippets.anthropic.ts },
        { label: 'Python', code: snippets.anthropic.py },
      ],
    },
  ]
}

export function buildGuideSnippets(
  baseUrl: string,
  key: string,
  model: string,
  options?: BuildGuideSnippetsOptions
): GuideSnippets {
  const authHeader = `Authorization: Bearer ${key}`
  const anthropicBase = baseUrl.replace(/\/openai\/v1\/?$/, '/anthropic')
  const anthropicV1 = `${anthropicBase}/v1`
  const modelsCurlNote = options?.multiGrantVkey
    ? `# multi-grant vkey：个人（主属 team）为裸注册名，其他授权工作区为 team-slug/name`
    : null
  const modelsCurlPrefix = modelsCurlNote ? `${modelsCurlNote}\n` : ''
  return {
    baseUrl,
    anthropicBaseUrl: anthropicBase,
    authHeader,
    modelsCurl: `${modelsCurlPrefix}curl "${baseUrl}/models" \\
  -H "${authHeader}"`,
    modelsCurlNote,
    streamHint: `// 流式：在请求体中设置 stream: true
{
  "model": "${model}",
  "stream": true,
  "messages": [{"role": "user", "content": "请用三句话介绍 AI Gateway 的作用。"}]
}`,
    openai: {
      endpoint: `POST ${baseUrl}/chat/completions`,
      authHeader,
      curl: `curl "${baseUrl}/chat/completions" \\
  -H "Content-Type: application/json" \\
  -H "${authHeader}" \\
  -d '{
    "model": "${model}",
    "messages": [{"role": "user", "content": "请用三句话介绍 AI Gateway 的作用。"}]
  }'`,
      curlStream: `curl -N "${baseUrl}/chat/completions" \\
  -H "Content-Type: application/json" \\
  -H "${authHeader}" \\
  -d '{
    "model": "${model}",
    "stream": true,
    "messages": [{"role": "user", "content": "请用三句话介绍 AI Gateway 的作用。"}]
  }'`,
      ts: `import OpenAI from "openai";

const client = new OpenAI({
  apiKey: "${key}",
  baseURL: "${baseUrl}",
});

const completion = await client.chat.completions.create({
  model: "${model}",
  messages: [{ role: "user", content: "请用三句话介绍 AI Gateway 的作用。" }],
});

console.log(completion.choices[0]?.message?.content);`,
      tsStream: `import OpenAI from "openai";

const client = new OpenAI({
  apiKey: "${key}",
  baseURL: "${baseUrl}",
});

const stream = await client.chat.completions.create({
  model: "${model}",
  stream: true,
  messages: [{ role: "user", content: "请用三句话介绍 AI Gateway 的作用。" }],
});

for await (const chunk of stream) {
  process.stdout.write(chunk.choices[0]?.delta?.content ?? "");
}`,
      py: `from openai import OpenAI

client = OpenAI(
    api_key="${key}",
    base_url="${baseUrl}",
)

completion = client.chat.completions.create(
    model="${model}",
    messages=[{"role": "user", "content": "请用三句话介绍 AI Gateway 的作用。"}],
)

print(completion.choices[0].message.content)`,
      pyStream: `from openai import OpenAI

client = OpenAI(
    api_key="${key}",
    base_url="${baseUrl}",
)

stream = client.chat.completions.create(
    model="${model}",
    stream=True,
    messages=[{"role": "user", "content": "请用三句话介绍 AI Gateway 的作用。"}],
)

for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="", flush=True)`,
      responseJson: `{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1717000000,
  "model": "${model}",
  "choices": [
    {
      "index": 0,
      "message": { "role": "assistant", "content": "AI Gateway 可以统一鉴权、路由和计费。" },
      "finish_reason": "stop"
    }
  ],
  "usage": { "prompt_tokens": 8, "completion_tokens": 2, "total_tokens": 10 }
}`,
      responseSse: `# 普通模型：仅 content
data: {"id":"chatcmpl-...","object":"chat.completion.chunk","model":"${model}","choices":[{"index":0,"delta":{"role":"assistant","content":"AI Gateway"},"finish_reason":null}]}

data: {"id":"chatcmpl-...","object":"chat.completion.chunk","model":"${model}","choices":[{"index":0,"delta":{"content":" 可以统一鉴权、路由和计费。"},"finish_reason":null}]}

# 推理模型（DeepSeek Reasoner / Qwen3+enable_thinking）可能先输出 reasoning_content：
# data: {"choices":[{"index":0,"delta":{"reasoning_content":"先分析依赖与风险..."}}]}

data: {"id":"chatcmpl-...","object":"chat.completion.chunk","model":"${model}","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":8,"completion_tokens":2,"total_tokens":10}}

data: [DONE]`,
    },
    anthropic: {
      endpoint: `POST ${anthropicV1}/messages`,
      authHeader: `x-api-key: ${key}`,
      curl: `curl "${anthropicV1}/messages" \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: ${key}" \\
  -H "anthropic-version: 2023-06-01" \\
  -d '{
    "model": "${model}",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "请用三句话介绍 AI Gateway 的作用。"}]
  }'`,
      curlStream: `curl -N "${anthropicV1}/messages" \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: ${key}" \\
  -H "anthropic-version: 2023-06-01" \\
  -d '{
    "model": "${model}",
    "max_tokens": 1024,
    "stream": true,
    "messages": [{"role": "user", "content": "请用三句话介绍 AI Gateway 的作用。"}]
  }'`,
      ts: `import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({
  apiKey: "${key}",
  baseURL: "${anthropicBase}",
});

const message = await client.messages.create({
  model: "${model}",
  max_tokens: 1024,
  messages: [{ role: "user", content: "请用三句话介绍 AI Gateway 的作用。" }],
});

console.log(
  message.content[0]?.type === "text" ? message.content[0].text : ""
);`,
      tsStream: `import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({
  apiKey: "${key}",
  baseURL: "${anthropicBase}",
});

const stream = await client.messages.stream({
  model: "${model}",
  max_tokens: 1024,
  messages: [{ role: "user", content: "请用三句话介绍 AI Gateway 的作用。" }],
});

for await (const event of stream) {
  if (
    event.type === "content_block_delta" &&
    event.delta.type === "text_delta"
  ) {
    process.stdout.write(event.delta.text);
  }
}`,
      py: `from anthropic import Anthropic

client = Anthropic(api_key="${key}", base_url="${anthropicBase}")

message = client.messages.create(
    model="${model}",
    max_tokens=1024,
    messages=[{"role": "user", "content": "请用三句话介绍 AI Gateway 的作用。"}],
)

print(message.content[0].text if message.content else "")`,
      pyStream: `from anthropic import Anthropic

client = Anthropic(api_key="${key}", base_url="${anthropicBase}")

with client.messages.stream(
    model="${model}",
    max_tokens=1024,
    messages=[{"role": "user", "content": "请用三句话介绍 AI Gateway 的作用。"}],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)`,
      responseJson: `{
  "id": "msg_...",
  "type": "message",
  "role": "assistant",
  "model": "${model}",
  "content": [{ "type": "text", "text": "AI Gateway 可以统一鉴权、路由和计费。" }],
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "usage": { "input_tokens": 8, "output_tokens": 2 }
}`,
      responseSse: `event: message_start
data: {"type":"message_start","message":{"id":"msg_...","role":"assistant","model":"${model}","content":[]}}

# Extended Thinking 时可能出现 thinking 块，再跟 text 块：
# event: content_block_delta
# data: {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"..."}}

event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"AI Gateway"}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" 可以统一鉴权、路由和计费。"}}

event: content_block_stop
data: {"type":"content_block_stop","index":0}

event: message_delta
data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":2}}

event: message_stop
data: {"type":"message_stop"}`,
    },
  }
}
