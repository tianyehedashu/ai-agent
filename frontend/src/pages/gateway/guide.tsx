/**
 * AI Gateway · 调用指南
 *
 * - 在线试调（PlaygroundCard）
 * - 调用配置：Base URL / 鉴权 / model / 流式字段
 * - 示例代码：OpenAI 兼容（/v1/chat/completions） + Anthropic 兼容（/v1/messages）
 *   每个风格内支持 curl / TS / Python，流式 toggle 同步切换示例代码与典型返回默认 Tab
 * - 典型返回：4 个 Tab 横向对比（OpenAI/Anthropic × 非流式/流式），用 Badge 突出 content-type
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import type React from 'react'

import { Link } from 'react-router-dom'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { PlaygroundCard } from '@/features/gateway-playground/playground-card'
import { useCopyToClipboardKeyed } from '@/hooks/use-copy-to-clipboard'
import { resolveGatewayV1BaseUrl } from '@/lib/gateway-v1-base-url'
import {
  Check,
  Copy,
  ExternalLink,
  FileText,
  Key,
  List,
  Sparkles,
  Terminal,
  Zap,
} from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

const PLACEHOLDER_KEY = 'sk-gw-your-virtual-key'
const PLACEHOLDER_MODEL = 'your-model-or-route-alias'

type ApiFlavor = 'openai' | 'anthropic'
type ResponseTab = 'openai-json' | 'openai-sse' | 'anthropic-json' | 'anthropic-sse'

interface FlavorSnippets {
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

interface Snippets {
  baseUrl: string
  authHeader: string
  modelsCurl: string
  streamHint: string
  openai: FlavorSnippets
  anthropic: FlavorSnippets
}

function buildSnippets(baseUrl: string, key: string, model: string): Snippets {
  const authHeader = `Authorization: Bearer ${key}`
  const anthropicBase = baseUrl.replace(/\/v1\/?$/, '')
  return {
    baseUrl,
    authHeader,
    modelsCurl: `curl "${baseUrl}/models" \\
  -H "${authHeader}"`,
    streamHint: `// 流式：在请求体中设置 stream: true
{
  "model": "${model}",
  "stream": true,
  "messages": [{"role": "user", "content": "Hello"}]
}`,
    openai: {
      endpoint: `POST ${baseUrl}/chat/completions`,
      authHeader,
      curl: `curl "${baseUrl}/chat/completions" \\
  -H "Content-Type: application/json" \\
  -H "${authHeader}" \\
  -d '{
    "model": "${model}",
    "messages": [{"role": "user", "content": "Hello"}]
  }'`,
      curlStream: `curl -N "${baseUrl}/chat/completions" \\
  -H "Content-Type: application/json" \\
  -H "${authHeader}" \\
  -d '{
    "model": "${model}",
    "stream": true,
    "messages": [{"role": "user", "content": "Hello"}]
  }'`,
      ts: `import OpenAI from "openai";

const client = new OpenAI({
  apiKey: "${key}",
  baseURL: "${baseUrl}",
});

const completion = await client.chat.completions.create({
  model: "${model}",
  messages: [{ role: "user", content: "Hello" }],
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
  messages: [{ role: "user", content: "Hello" }],
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
    messages=[{"role": "user", "content": "Hello"}],
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
    messages=[{"role": "user", "content": "Hello"}],
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
      "message": { "role": "assistant", "content": "Hello!" },
      "finish_reason": "stop"
    }
  ],
  "usage": { "prompt_tokens": 8, "completion_tokens": 2, "total_tokens": 10 }
}`,
      responseSse: `data: {"id":"chatcmpl-...","object":"chat.completion.chunk","model":"${model}","choices":[{"index":0,"delta":{"role":"assistant","content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-...","object":"chat.completion.chunk","model":"${model}","choices":[{"index":0,"delta":{"content":"!"},"finish_reason":null}]}

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
    "messages": [{"role": "user", "content": "Hello"}]
  }'`,
      curlStream: `curl -N "${baseUrl}/messages" \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: ${key}" \\
  -H "anthropic-version: 2023-06-01" \\
  -d '{
    "model": "${model}",
    "max_tokens": 1024,
    "stream": true,
    "messages": [{"role": "user", "content": "Hello"}]
  }'`,
      ts: `import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({
  apiKey: "${key}",
  baseURL: "${anthropicBase}",
});

const message = await client.messages.create({
  model: "${model}",
  max_tokens: 1024,
  messages: [{ role: "user", content: "Hello" }],
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
  messages: [{ role: "user", content: "Hello" }],
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
    messages=[{"role": "user", "content": "Hello"}],
)

print(message.content[0].text if message.content else "")`,
      pyStream: `from anthropic import Anthropic

client = Anthropic(api_key="${key}", base_url="${anthropicBase}")

with client.messages.stream(
    model="${model}",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)`,
      responseJson: `{
  "id": "msg_...",
  "type": "message",
  "role": "assistant",
  "model": "${model}",
  "content": [{ "type": "text", "text": "Hello!" }],
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "usage": { "input_tokens": 8, "output_tokens": 2 }
}`,
      responseSse: `event: message_start
data: {"type":"message_start","message":{"id":"msg_...","role":"assistant","model":"${model}","content":[]}}

event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"!"}}

event: content_block_stop
data: {"type":"content_block_stop","index":0}

event: message_delta
data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":2}}

event: message_stop
data: {"type":"message_stop"}`,
    },
  }
}

const QUICK_STEPS = [
  {
    step: 1,
    title: '创建虚拟 Key',
    description: '在「虚拟 Key」页创建 sk-gw-*，明文仅展示一次，请立即保存。',
    href: '/gateway/keys',
    linkLabel: '前往虚拟 Key',
  },
  {
    step: 2,
    title: '选择模型或路由',
    description: '请求中的 model 填已注册模型别名，或虚拟路由名称。',
    href: '/gateway/models',
    linkLabel: '查看模型',
  },
  {
    step: 3,
    title: '复制示例并调用',
    description: '将 Base URL 与 Key 填入 OpenAI / Anthropic SDK 或 curl 即可发起调用。',
    href: '#examples',
    linkLabel: '查看示例',
  },
] as const

const TROUBLESHOOTING = [
  {
    code: '401',
    title: '鉴权失败',
    hint: '检查 Bearer / x-api-key 是否正确、Key 是否已撤销。',
    href: '/gateway/keys',
    linkLabel: '虚拟 Key',
  },
  {
    code: '404',
    title: '模型不存在',
    hint: 'model 需与网关已注册别名或虚拟路由名一致。',
    href: '/gateway/models',
    linkLabel: '模型',
  },
  {
    code: '429',
    title: '限流',
    hint: '检查虚拟 Key 的 RPM/TPM 上限，或团队预算配额。',
    href: '/gateway/budgets',
    linkLabel: '预算配额',
  },
  {
    code: '5xx',
    title: '上游失败',
    hint: '多为凭据或上游不可用，先到调用日志查看 request_id 与错误详情。',
    href: '/gateway/logs',
    linkLabel: '调用日志',
  },
] as const

function preloadGatewayKeysPage(): void {
  void import('@/pages/gateway/keys')
}

export default function GatewayGuidePage(): React.JSX.Element {
  const [gatewayV1Base] = useState(resolveGatewayV1BaseUrl)
  const [activeModel, setActiveModel] = useState<string>(PLACEHOLDER_MODEL)
  const [apiFlavor, setApiFlavor] = useState<ApiFlavor>('openai')
  const [exampleStream, setExampleStream] = useState(true)
  const [responseTab, setResponseTab] = useState<ResponseTab>('openai-sse')

  const snippets = useMemo(
    () => buildSnippets(gatewayV1Base, PLACEHOLDER_KEY, activeModel || PLACEHOLDER_MODEL),
    [gatewayV1Base, activeModel]
  )
  const [copy, copiedKey] = useCopyToClipboardKeyed<string>()
  const handleCopy = useCallback(
    (key: string, text: string) => {
      void copy(text, key)
    },
    [copy]
  )
  const handlePlaygroundModelChange = useCallback((next: string) => {
    setActiveModel(next || PLACEHOLDER_MODEL)
  }, [])

  // 示例流式 / API 风格变化时，把典型返回 Tab 默认联动到对应组合，但仍允许独立切换
  useEffect(() => {
    setResponseTab(`${apiFlavor}-${exampleStream ? 'sse' : 'json'}` as ResponseTab)
  }, [apiFlavor, exampleStream])

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <h2 className="text-balance text-2xl font-semibold tracking-tight">调用指南</h2>
          <p className="max-w-2xl text-sm text-muted-foreground">
            兼容 OpenAI 与 Anthropic SDK。下方在线试调会为你自动准备一把虚拟 Key（
            <span className="font-mono" translate="no">
              sk-gw-*
            </span>
            ，仅本浏览器缓存），可直接调用团队模型、个人模型或
            <Link to="/gateway/routes" className="text-primary underline-offset-4 hover:underline">
              虚拟路由
            </Link>
            。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" asChild>
            <Link
              to="/gateway/keys"
              onMouseEnter={preloadGatewayKeysPage}
              onFocus={preloadGatewayKeysPage}
            >
              <Key className="mr-1.5 h-4 w-4" aria-hidden="true" />
              创建虚拟 Key
            </Link>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link to="/gateway/logs">
              <List className="mr-1.5 h-4 w-4" aria-hidden="true" />
              查看调用日志
            </Link>
          </Button>
        </div>
      </header>

      <PlaygroundCard baseUrl={gatewayV1Base} onModelChange={handlePlaygroundModelChange} />

      <section aria-labelledby="quick-start-heading">
        <h3 id="quick-start-heading" className="mb-3 text-sm font-medium text-muted-foreground">
          快速上手
        </h3>
        <div className="grid gap-3 md:grid-cols-3">
          {QUICK_STEPS.map((item) => (
            <Card key={item.step}>
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="h-6 w-6 justify-center rounded-full p-0">
                    {item.step}
                  </Badge>
                  <CardTitle className="text-base">{item.title}</CardTitle>
                </div>
                <CardDescription>{item.description}</CardDescription>
              </CardHeader>
              <CardContent>
                {item.href.startsWith('#') ? (
                  <a
                    href={item.href}
                    className="inline-flex items-center gap-1 text-sm text-primary underline-offset-4 hover:underline"
                  >
                    {item.linkLabel}
                  </a>
                ) : (
                  <Link
                    to={item.href}
                    className="inline-flex items-center gap-1 text-sm text-primary underline-offset-4 hover:underline"
                  >
                    {item.linkLabel}
                    <ExternalLink className="h-3 w-3" aria-hidden="true" />
                  </Link>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">调用配置</CardTitle>
          <CardDescription>
            兼容入口挂载在根路径{' '}
            <span className="font-mono" translate="no">
              /v1/*
            </span>
            ，与管理 API（
            <span className="font-mono" translate="no">
              /api/v1/gateway/*
            </span>
            ）不同。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <ConfigRow
            label="Base URL"
            value={snippets.baseUrl}
            mono
            copyKey="baseUrl"
            copied={copiedKey === 'baseUrl'}
            onCopy={handleCopy}
          />
          <ConfigRow
            label="OpenAI 鉴权 Header"
            value={snippets.openai.authHeader}
            mono
            copyKey="openaiAuthHeader"
            copied={copiedKey === 'openaiAuthHeader'}
            onCopy={handleCopy}
          />
          <ConfigRow
            label="Anthropic 鉴权 Header"
            value={snippets.anthropic.authHeader}
            mono
            hint="Anthropic 兼容亦支持 Authorization: Bearer；建议加 anthropic-version: 2023-06-01"
            copyKey="anthropicAuthHeader"
            copied={copiedKey === 'anthropicAuthHeader'}
            onCopy={handleCopy}
          />
          <ConfigRow
            label="model 字段"
            value={activeModel}
            mono
            hint={
              activeModel === PLACEHOLDER_MODEL
                ? '替换为模型页中的别名，或虚拟路由名称；在上方「在线试调」选择后会自动联动到示例。'
                : '已从「在线试调」联动；也可在模型页或虚拟路由页确认名称。'
            }
          />
          <ConfigRow
            label="流式 stream"
            value="true"
            mono
            hint="在 JSON body 中设置 stream: true，响应为 SSE（OpenAI: data: [DONE] ；Anthropic: event: message_stop）"
            copyKey="streamHint"
            copyText={snippets.streamHint}
            copied={copiedKey === 'streamHint'}
            onCopy={handleCopy}
          />
        </CardContent>
      </Card>

      <section id="examples" aria-labelledby="examples-heading" className="space-y-3">
        <h3 id="examples-heading" className="text-sm font-medium text-muted-foreground">
          示例代码
        </h3>
        <Card>
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-1">
                <CardTitle className="text-base">选择 API 风格 & 是否流式</CardTitle>
                <CardDescription>
                  顶部切换 API 风格 / 流式开关后，示例代码与下方「典型返回」会同步联动。
                </CardDescription>
              </div>
              <div className="flex items-center gap-2 rounded-md border bg-muted/40 px-3 py-1.5">
                <Zap
                  className={cn(
                    'h-4 w-4',
                    exampleStream ? 'text-amber-500' : 'text-muted-foreground'
                  )}
                  aria-hidden="true"
                />
                <Label htmlFor="example-stream" className="cursor-pointer text-sm">
                  流式（SSE）
                </Label>
                <Switch
                  id="example-stream"
                  checked={exampleStream}
                  onCheckedChange={setExampleStream}
                />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <Tabs
              value={apiFlavor}
              onValueChange={(v) => {
                setApiFlavor(v as ApiFlavor)
              }}
            >
              <TabsList>
                <TabsTrigger value="openai">OpenAI 兼容</TabsTrigger>
                <TabsTrigger value="anthropic">Anthropic 兼容</TabsTrigger>
              </TabsList>

              <TabsContent value="openai" className="space-y-3">
                <EndpointBadge
                  endpoint={snippets.openai.endpoint}
                  authHeader={snippets.openai.authHeader}
                  mode={exampleStream ? 'stream' : 'json'}
                  copyKey="openaiEndpoint"
                  copied={copiedKey === 'openaiEndpoint'}
                  onCopy={handleCopy}
                />
                <FlavorExamples
                  curl={exampleStream ? snippets.openai.curlStream : snippets.openai.curl}
                  ts={exampleStream ? snippets.openai.tsStream : snippets.openai.ts}
                  py={exampleStream ? snippets.openai.pyStream : snippets.openai.py}
                  keyPrefix={`openai-${exampleStream ? 'stream' : 'json'}`}
                  copiedKey={copiedKey}
                  onCopy={handleCopy}
                />
              </TabsContent>

              <TabsContent value="anthropic" className="space-y-3">
                <EndpointBadge
                  endpoint={snippets.anthropic.endpoint}
                  authHeader={snippets.anthropic.authHeader}
                  mode={exampleStream ? 'stream' : 'json'}
                  copyKey="anthropicEndpoint"
                  copied={copiedKey === 'anthropicEndpoint'}
                  onCopy={handleCopy}
                />
                <FlavorExamples
                  curl={exampleStream ? snippets.anthropic.curlStream : snippets.anthropic.curl}
                  ts={exampleStream ? snippets.anthropic.tsStream : snippets.anthropic.ts}
                  py={exampleStream ? snippets.anthropic.pyStream : snippets.anthropic.py}
                  keyPrefix={`anthropic-${exampleStream ? 'stream' : 'json'}`}
                  copiedKey={copiedKey}
                  onCopy={handleCopy}
                />
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">典型返回</CardTitle>
          <CardDescription>
            非流式为单个 JSON；流式为{' '}
            <span className="font-mono" translate="no">
              text/event-stream
            </span>
            （OpenAI 以{' '}
            <span className="font-mono" translate="no">
              data: [DONE]
            </span>{' '}
            结束，Anthropic 以{' '}
            <span className="font-mono" translate="no">
              event: message_stop
            </span>{' '}
            结束）。 完整响应可在上方「在线试调」的 <span className="font-medium">Raw JSON</span>{' '}
            视图查看。
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs
            value={responseTab}
            onValueChange={(v) => {
              setResponseTab(v as ResponseTab)
            }}
          >
            <TabsList className="flex h-auto flex-wrap gap-1">
              <ResponseTabTrigger value="openai-json" flavor="OpenAI" mode="json" />
              <ResponseTabTrigger value="openai-sse" flavor="OpenAI" mode="sse" />
              <ResponseTabTrigger value="anthropic-json" flavor="Anthropic" mode="json" />
              <ResponseTabTrigger value="anthropic-sse" flavor="Anthropic" mode="sse" />
            </TabsList>
            <TabsContent value="openai-json">
              <ResponseExample
                title="POST /v1/chat/completions"
                contentType="application/json"
                mode="json"
                code={snippets.openai.responseJson}
                copyKey="openaiResponseJson"
                copied={copiedKey === 'openaiResponseJson'}
                onCopy={handleCopy}
              />
            </TabsContent>
            <TabsContent value="openai-sse">
              <ResponseExample
                title="POST /v1/chat/completions（stream: true）"
                contentType="text/event-stream"
                mode="sse"
                code={snippets.openai.responseSse}
                copyKey="openaiResponseSse"
                copied={copiedKey === 'openaiResponseSse'}
                onCopy={handleCopy}
              />
            </TabsContent>
            <TabsContent value="anthropic-json">
              <ResponseExample
                title="POST /v1/messages"
                contentType="application/json"
                mode="json"
                code={snippets.anthropic.responseJson}
                copyKey="anthropicResponseJson"
                copied={copiedKey === 'anthropicResponseJson'}
                onCopy={handleCopy}
              />
            </TabsContent>
            <TabsContent value="anthropic-sse">
              <ResponseExample
                title="POST /v1/messages（stream: true）"
                contentType="text/event-stream"
                mode="sse"
                code={snippets.anthropic.responseSse}
                copyKey="anthropicResponseSse"
                copied={copiedKey === 'anthropicResponseSse'}
                onCopy={handleCopy}
              />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">查询可用模型</CardTitle>
          <CardDescription>
            使用{' '}
            <span className="font-mono" translate="no">
              GET /v1/models
            </span>{' '}
            列出当前 Key 可见模型；也可在
            <Link to="/gateway/models" className="text-primary underline-offset-4 hover:underline">
              模型
            </Link>
            、
            <Link to="/gateway/routes" className="text-primary underline-offset-4 hover:underline">
              虚拟路由
            </Link>
            页面确认名称。
          </CardDescription>
        </CardHeader>
        <CardContent>
          <CodeExampleCard
            title="curl"
            icon={Terminal}
            code={snippets.modelsCurl}
            copyKey="modelsCurl"
            copied={copiedKey === 'modelsCurl'}
            onCopy={handleCopy}
            embedded
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">常见问题</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {TROUBLESHOOTING.map((item, index) => (
            <div key={item.code}>
              {index > 0 ? <Separator className="mb-3" /> : null}
              <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-sm font-medium">
                    <Badge variant="outline" className="mr-2 font-mono" translate="no">
                      {item.code}
                    </Badge>
                    {item.title}
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">{item.hint}</p>
                </div>
                <Link
                  to={item.href}
                  className="shrink-0 text-sm text-primary underline-offset-4 hover:underline"
                >
                  {item.linkLabel} →
                </Link>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Alert>
        <AlertTitle>实用提示</AlertTitle>
        <AlertDescription className="space-y-2">
          <p>生产环境请在服务端保存并转发虚拟 Key，不要把 Key 写进前端 bundle 或浏览器请求。</p>
          <p>
            平台{' '}
            <span className="font-mono" translate="no">
              sk-*
            </span>
            （设置 → API 密钥）与管理 API 不同；OpenAI / Anthropic 兼容调用请使用此处的{' '}
            <span className="font-mono" translate="no">
              sk-gw-*
            </span>
            。
          </p>
          <p>
            Anthropic SDK 的{' '}
            <span className="font-mono" translate="no">
              baseURL
            </span>{' '}
            不要带{' '}
            <span className="font-mono" translate="no">
              /v1
            </span>
            ；curl 直接 POST{' '}
            <span className="font-mono" translate="no">
              /v1/messages
            </span>{' '}
            即可。
          </p>
          <p>
            调用异常时，优先在
            <Link to="/gateway/logs" className="text-primary underline-offset-4 hover:underline">
              调用日志
            </Link>
            按时间与 model 筛选排查。
          </p>
        </AlertDescription>
      </Alert>
    </div>
  )
}

function ConfigRow({
  label,
  value,
  hint,
  mono,
  copyKey,
  copyText,
  copied,
  onCopy,
}: Readonly<{
  label: string
  value: string
  hint?: string
  mono?: boolean
  copyKey?: string
  copyText?: string
  copied?: boolean
  onCopy?: (key: string, text: string) => void
}>): React.JSX.Element {
  const textToCopy = copyText ?? value
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <p
          className={cn('mt-0.5 break-all text-sm', mono && 'font-mono')}
          translate={mono ? 'no' : undefined}
        >
          {value}
        </p>
        {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
      </div>
      {copyKey && onCopy ? (
        <CopyButton
          copied={copied ?? false}
          label={`复制 ${label}`}
          onCopy={() => {
            onCopy(copyKey, textToCopy)
          }}
        />
      ) : null}
    </div>
  )
}

function EndpointBadge({
  endpoint,
  authHeader,
  mode,
  copyKey,
  copied,
  onCopy,
}: Readonly<{
  endpoint: string
  authHeader: string
  mode: 'json' | 'stream'
  copyKey: string
  copied: boolean
  onCopy: (key: string, text: string) => void
}>): React.JSX.Element {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/30 px-3 py-2 text-xs">
      <Badge variant="secondary" className="font-mono">
        {endpoint.split(' ')[0]}
      </Badge>
      <span className="font-mono text-foreground/90" translate="no">
        {endpoint.split(' ').slice(1).join(' ')}
      </span>
      {mode === 'stream' ? (
        <Badge variant="outline" className="gap-1 border-amber-500/40 text-amber-600">
          <Zap className="h-3 w-3" aria-hidden="true" />
          流式 SSE
        </Badge>
      ) : (
        <Badge variant="outline" className="gap-1">
          <FileText className="h-3 w-3" aria-hidden="true" />
          非流式 JSON
        </Badge>
      )}
      <Separator orientation="vertical" className="h-4" />
      <span className="text-muted-foreground">鉴权</span>
      <span className="font-mono text-foreground/90" translate="no">
        {authHeader}
      </span>
      <button
        type="button"
        onClick={() => {
          onCopy(copyKey, endpoint)
        }}
        className="ml-auto inline-flex items-center gap-1 text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        aria-label="复制端点"
      >
        {copied ? (
          <Check className="h-3 w-3" aria-hidden="true" />
        ) : (
          <Copy className="h-3 w-3" aria-hidden="true" />
        )}
        {copied ? '已复制' : '复制端点'}
      </button>
    </div>
  )
}

function FlavorExamples({
  curl,
  ts,
  py,
  keyPrefix,
  copiedKey,
  onCopy,
}: Readonly<{
  curl: string
  ts: string
  py: string
  keyPrefix: string
  copiedKey: string | null
  onCopy: (key: string, text: string) => void
}>): React.JSX.Element {
  const curlKey = `${keyPrefix}-curl`
  const tsKey = `${keyPrefix}-ts`
  const pyKey = `${keyPrefix}-py`
  return (
    <div className="space-y-3">
      <CodeExampleCard
        title="curl"
        icon={Terminal}
        code={curl}
        copyKey={curlKey}
        copied={copiedKey === curlKey}
        onCopy={onCopy}
      />
      <CodeExampleCard
        title="TypeScript（SDK）"
        code={ts}
        copyKey={tsKey}
        copied={copiedKey === tsKey}
        onCopy={onCopy}
      />
      <CodeExampleCard
        title="Python（SDK）"
        code={py}
        copyKey={pyKey}
        copied={copiedKey === pyKey}
        onCopy={onCopy}
      />
    </div>
  )
}

function ResponseTabTrigger({
  value,
  flavor,
  mode,
}: Readonly<{
  value: ResponseTab
  flavor: 'OpenAI' | 'Anthropic'
  mode: 'json' | 'sse'
}>): React.JSX.Element {
  return (
    <TabsTrigger value={value} className="h-9 gap-1.5 px-3 text-xs">
      {mode === 'sse' ? (
        <Zap className="h-3.5 w-3.5 text-amber-500" aria-hidden="true" />
      ) : (
        <FileText className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
      )}
      <span className="font-medium">{flavor}</span>
      <span className="text-muted-foreground">·</span>
      <span>{mode === 'sse' ? '流式' : '非流式'}</span>
    </TabsTrigger>
  )
}

function ResponseExample({
  title,
  contentType,
  mode,
  code,
  copyKey,
  copied,
  onCopy,
}: Readonly<{
  title: string
  contentType: string
  mode: 'json' | 'sse'
  code: string
  copyKey: string
  copied: boolean
  onCopy: (key: string, text: string) => void
}>): React.JSX.Element {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {mode === 'sse' ? (
          <Badge variant="outline" className="gap-1 border-amber-500/40 text-amber-600">
            <Zap className="h-3 w-3" aria-hidden="true" />
            流式 SSE
          </Badge>
        ) : (
          <Badge variant="outline" className="gap-1">
            <FileText className="h-3 w-3" aria-hidden="true" />
            非流式 JSON
          </Badge>
        )}
        <span className="font-mono text-foreground/90" translate="no">
          {title}
        </span>
        <Badge variant="secondary" className="font-mono">
          Content-Type: {contentType}
        </Badge>
        {mode === 'sse' ? (
          <Badge variant="secondary" className="gap-1">
            <Sparkles className="h-3 w-3" aria-hidden="true" />
            增量推送 / 多帧
          </Badge>
        ) : (
          <Badge variant="secondary">一次性返回</Badge>
        )}
      </div>
      <CodeExampleCard
        title={mode === 'sse' ? '响应（按帧解析）' : '响应'}
        icon={mode === 'sse' ? Zap : FileText}
        code={code}
        copyKey={copyKey}
        copied={copied}
        onCopy={onCopy}
        embedded
      />
    </div>
  )
}

function CodeExampleCard({
  title,
  code,
  copyKey,
  copied,
  onCopy,
  icon: Icon = Terminal,
  embedded,
}: Readonly<{
  title: string
  code: string
  copyKey: string
  copied: boolean
  onCopy: (key: string, text: string) => void
  icon?: React.ComponentType<{ className?: string }>
  embedded?: boolean
}>): React.JSX.Element {
  const inner = (
    <div className="relative">
      <div className="absolute right-2 top-2 z-10">
        <CopyButton
          copied={copied}
          label={`复制 ${title}`}
          onCopy={() => {
            onCopy(copyKey, code)
          }}
        />
      </div>
      <pre className="max-h-72 overflow-auto rounded-md border bg-muted/50 p-4 pr-24 text-xs leading-relaxed">
        <code translate="no">{code}</code>
      </pre>
    </div>
  )

  if (embedded) {
    return inner
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Icon className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">{inner}</CardContent>
    </Card>
  )
}

function CopyButton({
  copied,
  label,
  onCopy,
}: Readonly<{
  copied: boolean
  label: string
  onCopy: () => void
}>): React.JSX.Element {
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className="h-8 gap-1.5"
      aria-label={label}
      onClick={onCopy}
    >
      {copied ? (
        <>
          <Check className="h-3.5 w-3.5" aria-hidden="true" />
          已复制
        </>
      ) : (
        <>
          <Copy className="h-3.5 w-3.5" aria-hidden="true" />
          复制
        </>
      )}
    </Button>
  )
}
