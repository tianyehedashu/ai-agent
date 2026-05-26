/**
 * 调用指南 · 按 Playground 试调模式生成 curl / TS / Python 示例
 */

import {
  PLAYGROUND_EXAMPLE_IMAGE_URL,
  PLAYGROUND_EXAMPLE_PROMPTS,
  PLAYGROUND_EXAMPLE_VIDEO_REF_URL,
} from '@/features/gateway-playground/playground-example-content'
import type { PlaygroundMode } from '@/features/gateway-playground/playground-mode-filter'
import {
  buildImageGenRequestBody,
  buildVideoGenRequestBody,
  buildVisionRequestBody,
} from '@/features/gateway-playground/playground-request'
import { defaultImageGenSizeForProvider } from '@/features/gateway-shared/image-gen-size-presets'

export interface GuideModeSnippet {
  endpoint: string
  curl: string
  ts: string
  py: string
  hint: string | null
}

export const GUIDE_MODE_HINTS: Record<PlaygroundMode, string | null> = {
  chat: null,
  vision: '需注册支持视觉理解（model_types 含 image）的 chat 模型别名。',
  image_gen: '需注册 capability=image 或 model_types 含 image_gen 的模型别名。',
  video_gen: '需注册 capability=video_generation 的模型别名。',
}

function formatJsonBody(body: Record<string, unknown>): string {
  return JSON.stringify(body, null, 2)
}

function curlPostJson(
  url: string,
  authHeader: string,
  body: Record<string, unknown>,
  stream = false
): string {
  const streamFlag = stream ? '-N ' : ''
  return `curl ${streamFlag}"${url}" \\
  -H "Content-Type: application/json" \\
  -H "${authHeader}" \\
  -d '${formatJsonBody(body)}'`
}

function buildVisionSnippets(baseUrl: string, key: string, model: string): GuideModeSnippet {
  const authHeader = `Authorization: Bearer ${key}`
  const url = `${baseUrl}/chat/completions`
  const visionPrompt = PLAYGROUND_EXAMPLE_PROMPTS.vision
  const body = buildVisionRequestBody({
    model,
    prompt: visionPrompt,
    imageUrl: PLAYGROUND_EXAMPLE_IMAGE_URL,
    stream: false,
  })

  return {
    endpoint: `POST ${url}`,
    curl: curlPostJson(url, authHeader, body),
    ts: `import OpenAI from "openai";

const client = new OpenAI({
  apiKey: "${key}",
  baseURL: "${baseUrl}",
});

const completion = await client.chat.completions.create({
  model: "${model}",
  messages: [{
    role: "user",
    content: [
      { type: "text", text: "${visionPrompt}" },
      { type: "image_url", image_url: { url: "${PLAYGROUND_EXAMPLE_IMAGE_URL}" } },
    ],
  }],
});

console.log(completion.choices[0]?.message?.content);`,
    py: `from openai import OpenAI

client = OpenAI(
    api_key="${key}",
    base_url="${baseUrl}",
)

completion = client.chat.completions.create(
    model="${model}",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "${visionPrompt}"},
            {"type": "image_url", "image_url": {"url": "${PLAYGROUND_EXAMPLE_IMAGE_URL}"}},
        ],
    }],
)

print(completion.choices[0].message.content)`,
    hint: GUIDE_MODE_HINTS.vision,
  }
}

function buildImageGenSnippets(baseUrl: string, key: string, model: string): GuideModeSnippet {
  const authHeader = `Authorization: Bearer ${key}`
  const url = `${baseUrl}/images/generations`
  const imagePrompt = PLAYGROUND_EXAMPLE_PROMPTS.image_gen
  const size = defaultImageGenSizeForProvider(undefined)
  const body = buildImageGenRequestBody({
    model,
    prompt: imagePrompt,
    size,
    n: 1,
    responseFormat: 'url',
  })

  return {
    endpoint: `POST ${url}`,
    curl: curlPostJson(url, authHeader, body),
    ts: `import OpenAI from "openai";

const client = new OpenAI({
  apiKey: "${key}",
  baseURL: "${baseUrl}",
});

const result = await client.images.generate({
  model: "${model}",
  prompt: "${imagePrompt}",
  size: "${size}",
  n: 1,
});

console.log(result.data[0]?.url);`,
    py: `from openai import OpenAI

client = OpenAI(
    api_key="${key}",
    base_url="${baseUrl}",
)

result = client.images.generate(
    model="${model}",
    prompt="${imagePrompt}",
    size="${size}",
    n=1,
)

print(result.data[0].url)`,
    hint: GUIDE_MODE_HINTS.image_gen,
  }
}

function buildVideoGenSnippets(baseUrl: string, key: string, model: string): GuideModeSnippet {
  const authHeader = `Authorization: Bearer ${key}`
  const url = `${baseUrl}/videos`
  const videoPrompt = PLAYGROUND_EXAMPLE_PROMPTS.video_gen
  const body = buildVideoGenRequestBody({
    model,
    prompt: videoPrompt,
    imageUrl: PLAYGROUND_EXAMPLE_VIDEO_REF_URL,
  })

  return {
    endpoint: `POST ${url}`,
    curl: curlPostJson(url, authHeader, body),
    ts: `// OpenAI SDK 尚未统一 videos 端点，使用 fetch 调用 Gateway OpenAI 兼容面
const response = await fetch("${url}", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: "Bearer ${key}",
  },
  body: JSON.stringify({
    model: "${model}",
    prompt: "${videoPrompt}",
    image: "${PLAYGROUND_EXAMPLE_VIDEO_REF_URL}", // 可选：图生视频参考图
  }),
});

const result = await response.json();
console.log(result);`,
    py: `import httpx

response = httpx.post(
    "${url}",
    headers={
        "Authorization": "Bearer ${key}",
        "Content-Type": "application/json",
    },
    json={
        "model": "${model}",
        "prompt": "${videoPrompt}",
        "image": "${PLAYGROUND_EXAMPLE_VIDEO_REF_URL}",  # 可选：图生视频参考图
    },
    timeout=300.0,
)
print(response.json())`,
    hint: GUIDE_MODE_HINTS.video_gen,
  }
}

/** 非 chat 模式的 OpenAI 兼容示例（vision / image_gen / video_gen） */
export function buildMediaModeSnippets(
  baseUrl: string,
  key: string,
  model: string,
  mode: Exclude<PlaygroundMode, 'chat'>
): GuideModeSnippet {
  switch (mode) {
    case 'vision':
      return buildVisionSnippets(baseUrl, key, model)
    case 'image_gen':
      return buildImageGenSnippets(baseUrl, key, model)
    case 'video_gen':
      return buildVideoGenSnippets(baseUrl, key, model)
    default: {
      const _exhaustive: never = mode
      return _exhaustive
    }
  }
}
