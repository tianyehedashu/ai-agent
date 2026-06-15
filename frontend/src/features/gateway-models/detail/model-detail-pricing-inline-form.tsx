import type React from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { providerLabel } from '@/features/gateway-credentials/provider-schemas'
import { Cloud, Loader2, Tags, X } from '@/lib/lucide-icons'
import type { DisplayCurrency } from '@/types/money'

function currencySymbol(currency: DisplayCurrency): string {
  return currency === 'CNY' ? '¥' : '$'
}

interface PricingInlineFormShellProps {
  icon: React.ReactNode
  title: string
  subtitle?: string
  borderClass: string
  pending: boolean
  canSubmit: boolean
  onCancel: () => void
  onSubmit: () => void
  children: React.ReactNode
}

export function PricingInlineFormShell({
  icon,
  title,
  subtitle,
  borderClass,
  pending,
  canSubmit,
  onCancel,
  onSubmit,
  children,
}: PricingInlineFormShellProps): React.JSX.Element {
  return (
    <div className={`space-y-3 rounded-md border p-3 ${borderClass}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-2">
          {icon}
          <div className="min-w-0 space-y-0.5">
            <p className="text-sm font-medium leading-tight">{title}</p>
            {subtitle ? (
              <p className="text-[11px] leading-snug text-muted-foreground">{subtitle}</p>
            ) : null}
          </div>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0"
          onClick={onCancel}
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>
      {children}
      <div className="flex justify-end gap-2 border-t border-border/40 pt-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-7 text-xs"
          onClick={onCancel}
        >
          取消
        </Button>
        <Button
          type="button"
          size="sm"
          className="h-7 text-xs"
          disabled={!canSubmit}
          onClick={onSubmit}
        >
          {pending ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}
          保存
        </Button>
      </div>
    </div>
  )
}

export function PricingModelKeyCard({
  provider,
  upstreamModel,
  capability,
  borderClass = 'border-amber-500/20',
}: {
  provider: string
  upstreamModel: string
  capability: string
  borderClass?: string
}): React.JSX.Element {
  return (
    <div className={`rounded-md border bg-background/80 px-3 py-2 ${borderClass}`}>
      <p className="text-xs font-medium text-foreground">{providerLabel(provider)}</p>
      <p className="mt-1 truncate font-mono text-[11px] text-muted-foreground">
        {provider}/{upstreamModel}
      </p>
      <p className="mt-1 text-[10px] text-muted-foreground">能力 · {capability || 'chat'}</p>
    </div>
  )
}

export function PricingCurrencyField({
  label,
  currency,
  value,
  placeholder,
  onChange,
}: {
  label: string
  currency: DisplayCurrency
  value: string
  placeholder?: string
  onChange: (value: string) => void
}): React.JSX.Element {
  const symbol = currencySymbol(currency)

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <Label className="text-xs">{label}</Label>
        <span className="shrink-0 rounded bg-muted/60 px-1.5 py-0.5 text-[10px] tabular-nums text-muted-foreground">
          {symbol} / 1M tokens
        </span>
      </div>
      <div className="relative">
        <span
          aria-hidden
          className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-sm text-muted-foreground"
        >
          {symbol}
        </span>
        <Input
          className="h-9 pl-7 tabular-nums"
          type="number"
          inputMode="decimal"
          min="0"
          step="0.0001"
          placeholder={placeholder ?? '0.0000'}
          value={value}
          onChange={(event) => {
            onChange(event.target.value)
          }}
        />
      </div>
    </div>
  )
}

export function downstreamPricingFormIcon(): React.JSX.Element {
  return (
    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-emerald-500/15 text-emerald-700 dark:text-emerald-300">
      <Tags className="h-3.5 w-3.5" />
    </div>
  )
}

export function upstreamPricingFormIcon(): React.JSX.Element {
  return (
    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-amber-500/15 text-amber-700 dark:text-amber-300">
      <Cloud className="h-3.5 w-3.5" />
    </div>
  )
}

export const DOWNSTREAM_PRICING_FORM_BORDER = 'border-emerald-500/25 bg-emerald-500/[0.04]'
export const UPSTREAM_PRICING_FORM_BORDER = 'border-amber-500/30 bg-amber-500/[0.06]'
