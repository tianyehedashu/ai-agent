/**
 * 调用指南 · 按第三方客户端维度的集成配置
 */

import { memo } from 'react'
import type React from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Check, Copy, Terminal } from '@/lib/lucide-icons'
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
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
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
      <pre className="overflow-x-auto rounded-md border bg-muted/50 p-3 text-xs leading-relaxed">
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
  return (
    <Card className="border-border/60 bg-background shadow-sm">
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center gap-2 text-base">
          <Terminal className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          第三方客户端集成
        </CardTitle>
        <p className="text-sm text-muted-foreground">{keyHintText}</p>
      </CardHeader>
      <CardContent className="pt-0">
        <Tabs defaultValue={defaultTab}>
          <TabsList className="flex h-auto flex-wrap gap-1">
            {clients.map((client) => (
              <TabsTrigger key={client.id} value={client.id} className="text-xs">
                {client.title}
              </TabsTrigger>
            ))}
          </TabsList>
          {clients.map((client) => (
            <TabsContent key={client.id} value={client.id} className="space-y-3 pt-3">
              <p className="text-sm text-muted-foreground">{client.summary}</p>
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
            </TabsContent>
          ))}
        </Tabs>
      </CardContent>
    </Card>
  )
})
