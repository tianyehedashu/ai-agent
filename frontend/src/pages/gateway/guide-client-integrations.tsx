/**
 * 调用指南 · 按第三方客户端维度的集成配置
 */

import { memo } from 'react'
import type React from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Check, Copy, Terminal } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'
import type { ClientIntegration } from '@/pages/gateway/guide-snippets'

function ClientIntegrationCodeBlock({
  label,
  code,
  copyKey,
  copiedKey,
  onCopy,
}: Readonly<{
  label: string
  code: string
  copyKey: string
  copiedKey: string | null
  onCopy: (key: string, text: string) => void
}>): React.JSX.Element {
  const copied = copiedKey === copyKey
  return (
    <div className="overflow-hidden rounded-xl border border-border/70 bg-muted/20">
      <div className="flex items-center justify-between gap-2 border-b border-border/60 bg-background/55 px-3 py-2">
        <p className="text-xs font-semibold text-foreground">{label}</p>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          aria-label={`复制 ${label}`}
          onClick={() => {
            onCopy(copyKey, code)
          }}
        >
          {copied ? (
            <Check className="h-3.5 w-3.5" aria-hidden="true" />
          ) : (
            <Copy className="h-3.5 w-3.5" aria-hidden="true" />
          )}
        </Button>
      </div>
      <pre className="max-h-72 overflow-auto p-3 text-xs leading-relaxed">
        <code translate="no">{code}</code>
      </pre>
    </div>
  )
}

export type GuideClientIntegrationsKeyHint = 'placeholder' | 'revealing' | 'revealed'

export const GuideClientIntegrationsSection = memo(function GuideClientIntegrationsSection({
  clients,
  copiedKey,
  onCopy,
  keyHint = 'placeholder',
}: Readonly<{
  clients: ClientIntegration[]
  copiedKey: string | null
  onCopy: (key: string, text: string) => void
  keyHint?: GuideClientIntegrationsKeyHint
}>): React.JSX.Element {
  const defaultTab = clients[0]?.id ?? 'claude-code'
  const keyHintText =
    keyHint === 'revealed'
      ? '以下片段已使用上方「在线试调」中 reveal 的虚拟 Key。'
      : keyHint === 'revealing'
        ? '正在加载虚拟 Key 明文，片段暂为占位符…'
        : '在上方「在线试调」选择虚拟 Key 并 reveal 后，片段将自动替换为真实 Key；否则为占位符。'
  const keyHintVariant =
    keyHint === 'revealed' ? 'success' : keyHint === 'revealing' ? 'info' : 'secondary'
  return (
    <Card className="border-border/60 bg-card/95 shadow-sm shadow-black/[0.03] dark:shadow-black/20">
      <CardHeader className="pb-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Terminal className="h-4 w-4 text-primary" aria-hidden="true" />
              第三方客户端集成
            </CardTitle>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">{keyHintText}</p>
          </div>
          <Badge variant={keyHintVariant} className="w-fit">
            {keyHint === 'revealed' ? '真实 Key' : keyHint === 'revealing' ? '载入中' : '占位符'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <Tabs defaultValue={defaultTab}>
          <TabsList className="grid h-auto grid-cols-2 gap-1 p-1 lg:grid-cols-4">
            {clients.map((client) => (
              <TabsTrigger
                key={client.id}
                value={client.id}
                className={cn('h-auto justify-start px-3 py-2 text-left text-xs')}
              >
                {client.title}
              </TabsTrigger>
            ))}
          </TabsList>
          <div className="pt-4">
            {clients.map((client) => (
              <TabsContent key={client.id} value={client.id} className="mt-0 space-y-4">
                <div className="rounded-xl border border-border/60 bg-background/45 px-4 py-3">
                  <p className="text-sm leading-6 text-muted-foreground">{client.summary}</p>
                </div>
                <div className="grid gap-4">
                  {client.blocks.map((block) => (
                    <ClientIntegrationCodeBlock
                      key={`${client.id}-${block.label}`}
                      label={block.label}
                      code={block.code}
                      copyKey={`client-${client.id}-${block.label}`}
                      copiedKey={copiedKey}
                      onCopy={onCopy}
                    />
                  ))}
                </div>
              </TabsContent>
            ))}
          </div>
        </Tabs>
      </CardContent>
    </Card>
  )
})
