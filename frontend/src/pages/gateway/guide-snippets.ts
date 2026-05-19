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
  streamHint: string
  openai: FlavorSnippets
  anthropic: FlavorSnippets
}

export function buildGuideSnippets(baseUrl: string, key: string, model: string): GuideSnippets {
  const authHeader = `Authorization: Bearer ${key}`
  const anthropicBase = baseUrl.replace(/\/v1\/?$/, '')
  return {
    baseUrl,
    anthropicBaseUrl: anthropicBase,
    authHeader,
    modelsCurl: `curl "${baseUrl}/models" \\
  -H "${authHeader}"`,
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
      responseSse: `data: {"id":"chatcmpl-...","object":"chat.completion.chunk","model":"${model}","choices":[{"index":0,"delta":{"role":"assistant","content":"AI Gateway"},"finish_reason":null}]}

data: {"id":"chatcmpl-...","object":"chat.completion.chunk","model":"${model}","choices":[{"index":0,"delta":{"content":" 可以统一鉴权、路由和计费。"},"finish_reason":null}]}

data: {"id":"chatcmpl-...","object":"chat.completion.chunk","model":"${model}","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":8,"completion_tokens":2,"total_tokens":10}}

data: [DONE]`,
    },
    anthropic: {
      endpoint: `POST ${baseUrl}/messages`,
      authHeader: `x-api-key: ${key}`,
      curl: `curl "${baseUrl}/messages" \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: ${key}" \\
  -H "anthropic-version: 2023-06-01" \\
  -d '{
    "model": "${model}",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "请用三句话介绍 AI Gateway 的作用。"}]
  }'`,
      curlStream: `curl -N "${baseUrl}/messages" \\
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
