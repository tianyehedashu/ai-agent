import { useEffect, useState } from 'react'

import type { QuotaRule } from '@/api/gateway/quota-rules'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { formatQuotaRulePeriodWindow } from '@/features/gateway-budget/quota-rule-utils'
import { formatQuotaTokens } from '@/features/gateway-budget/quota-token-display'
import {
  buildQuotaRuleSourceMutationBody,
  buildQuotaUsageAdjustmentBody,
  useQuotaUsageAdjust,
} from '@/features/gateway-budget/use-quota-usage-adjust'

import type { QuotaCenterMode } from './use-quota-center'

interface QuotaUsageAdjustDialogProps {
  teamId: string
  mode: QuotaCenterMode
  rule: QuotaRule | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function QuotaUsageAdjustDialog({
  teamId,
  mode,
  rule,
  open,
  onOpenChange,
}: QuotaUsageAdjustDialogProps): React.JSX.Element {
  const [usd, setUsd] = useState('')
  const [tokens, setTokens] = useState('')
  const [requests, setRequests] = useState('')
  const [images, setImages] = useState('')
  const { adjustUsage, resetWindow, pending } = useQuotaUsageAdjust({
    teamId,
    mode,
    onSuccess: () => {
      onOpenChange(false)
    },
  })

  useEffect(() => {
    if (!rule || !open) return
    const body = buildQuotaUsageAdjustmentBody(rule)
    setUsd(String(body.current_usd ?? 0))
    setTokens(String(body.current_tokens ?? 0))
    setRequests(String(body.current_requests ?? 0))
    setImages(String(body.current_images ?? 0))
  }, [rule, open])

  const periodLabel = rule ? formatQuotaRulePeriodWindow(rule) : null
  const showImages = rule ? rule.limits.limit_images !== null : false

  const handleSave = (): void => {
    if (!rule) return
    adjustUsage({
      ...buildQuotaRuleSourceMutationBody(rule),
      mode: 'set',
      current_usd: Number.parseFloat(usd) || 0,
      current_tokens: Number.parseInt(tokens, 10) || 0,
      current_requests: Number.parseInt(requests, 10) || 0,
      current_images: Number.parseInt(images, 10) || 0,
    })
  }

  const handleReset = (): void => {
    if (!rule) return
    if (!window.confirm('确定将本周期已用额度清零？')) return
    resetWindow(rule)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>设置本周期已用额度</DialogTitle>
          <DialogDescription>
            手工校正当前窗口的已用用量；平台规则会同步执法计数。若展示值仍偏高，可能是请求日志汇总更高。
          </DialogDescription>
        </DialogHeader>
        {periodLabel ? <p className="text-xs text-muted-foreground">{periodLabel}</p> : null}
        <div className="grid gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="quota-usage-usd">已用费用 (USD)</Label>
            <Input
              id="quota-usage-usd"
              inputMode="decimal"
              className="tabular-nums"
              value={usd}
              onChange={(e) => {
                setUsd(e.target.value)
              }}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="quota-usage-tokens">已用 Token</Label>
            <Input
              id="quota-usage-tokens"
              inputMode="numeric"
              className="tabular-nums"
              value={tokens}
              onChange={(e) => {
                setTokens(e.target.value)
              }}
            />
            {tokens.trim() ? (
              <p className="text-[11px] text-muted-foreground">
                ≈ {formatQuotaTokens(Number.parseInt(tokens, 10) || 0)}
              </p>
            ) : null}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="quota-usage-requests">已用请求数</Label>
            <Input
              id="quota-usage-requests"
              inputMode="numeric"
              className="tabular-nums"
              value={requests}
              onChange={(e) => {
                setRequests(e.target.value)
              }}
            />
          </div>
          {showImages ? (
            <div className="space-y-1.5">
              <Label htmlFor="quota-usage-images">已用图片张数</Label>
              <Input
                id="quota-usage-images"
                inputMode="numeric"
                className="tabular-nums"
                value={images}
                onChange={(e) => {
                  setImages(e.target.value)
                }}
              />
            </div>
          ) : null}
        </div>
        <DialogFooter className="flex-col gap-2 sm:flex-row sm:justify-between">
          <Button type="button" variant="outline" disabled={pending || !rule} onClick={handleReset}>
            清零本周期
          </Button>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                onOpenChange(false)
              }}
            >
              取消
            </Button>
            <Button type="button" disabled={pending || !rule} onClick={handleSave}>
              保存
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
