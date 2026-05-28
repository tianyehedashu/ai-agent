/**
 * 虚拟 Key 明文查看对话框（调用 GET …/keys/{id}/reveal）
 */

import { useState } from 'react'

import { useQuery } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useToast } from '@/hooks/use-toast'
import { formatGatewayManagementError } from '@/lib/gateway-api-error'
import { Check, Copy } from '@/lib/lucide-icons'

export interface VirtualKeyRevealTarget {
  id: string
  name: string
  masked_key: string
  team_id?: string
}

export interface VirtualKeyRevealDialogProps {
  teamId: string
  teamDisplayName?: string
  target: VirtualKeyRevealTarget | null
  onClose: () => void
}

export function VirtualKeyRevealDialog({
  teamId,
  teamDisplayName,
  target,
  onClose,
}: Readonly<VirtualKeyRevealDialogProps>): React.JSX.Element {
  const { toast } = useToast()
  const [copied, setCopied] = useState(false)

  const revealQuery = useQuery({
    queryKey: ['gateway', 'keys', teamId, target?.id, 'reveal'] as const,
    queryFn: () => {
      if (!target) throw new Error('missing key id')
      return gatewayApi.revealKey(teamId, target.id)
    },
    enabled: target !== null,
    retry: false,
  })

  const plainKey = revealQuery.data?.plain_key ?? null
  const revealFailed = revealQuery.isError && target !== null

  return (
    <Dialog
      open={target !== null}
      onOpenChange={(open) => {
        if (!open) {
          setCopied(false)
          onClose()
        }
      }}
    >
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{target ? `「${target.name}」完整 Key` : '完整 Key'}</DialogTitle>
          <DialogDescription>
            {target ? (
              <>
                掩码：<span className="font-mono">{target.masked_key}</span>
              </>
            ) : (
              '请妥善保管虚拟 Key'
            )}
          </DialogDescription>
        </DialogHeader>

        {teamDisplayName ? (
          <div className="rounded-md border bg-muted/20 px-3 py-2 text-sm">
            <span className="text-muted-foreground">绑定工作区：</span>
            <span className="font-medium">{teamDisplayName}</span>
            {target?.team_id ? (
              <span
                className="mt-1 block font-mono text-xs text-muted-foreground"
                title={target.team_id}
              >
                {target.team_id}
              </span>
            ) : (
              <span className="mt-1 block font-mono text-xs text-muted-foreground" title={teamId}>
                {teamId}
              </span>
            )}
          </div>
        ) : null}

        <div className="space-y-4">
          {plainKey ? (
            <>
              <div className="rounded-lg bg-muted p-4">
                <div className="flex items-center justify-between gap-2">
                  <code className="flex-1 break-all font-mono text-sm">{plainKey}</code>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="shrink-0"
                    aria-label="复制完整 Key"
                    onClick={() => {
                      void navigator.clipboard.writeText(plainKey)
                      setCopied(true)
                      setTimeout(() => {
                        setCopied(false)
                      }, 2000)
                      toast({ title: '已复制到剪贴板' })
                    }}
                  >
                    {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  </Button>
                </div>
              </div>
              <p className="text-sm text-muted-foreground">
                请将此 Key 保存在安全的地方。关闭对话框后，仍可在列表中再次查看。
              </p>
            </>
          ) : revealFailed ? (
            <p className="text-sm text-destructive">
              {formatGatewayManagementError(
                revealQuery.error instanceof Error
                  ? revealQuery.error
                  : new Error('无法显示完整 Key')
              )}
            </p>
          ) : (
            <div className="rounded-lg border border-dashed p-6 text-center">
              <div className="mx-auto mb-4 h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              <p className="text-sm text-muted-foreground">正在解密虚拟 Key…</p>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            关闭
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
