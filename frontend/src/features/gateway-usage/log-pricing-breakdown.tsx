import type React from 'react'

import { Link } from 'react-router-dom'

import type { GatewayLogDetail } from '@/api/gateway'
import { GATEWAY_DISPLAY_CURRENCY } from '@/features/gateway-pricing/display-currency'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { coalesceMoney, formatMoney } from '@/lib/money'
import type { DisplayCurrency } from '@/types/money'

interface LogPricingBreakdownProps {
  detail: GatewayLogDetail
}

export function LogPricingBreakdown({ detail }: LogPricingBreakdownProps): React.JSX.Element {
  const currency = GATEWAY_DISPLAY_CURRENCY
  const { isAdmin } = useGatewayPermission()
  const snap = detail.pricing_snapshot
  const costUsd = coalesceMoney(detail.cost_usd)
  const revenueUsd = coalesceMoney(detail.revenue_usd ?? detail.cost_usd)
  const marginUsd = revenueUsd - costUsd
  const fxRate = snap && typeof snap.fx_rate_used === 'string' ? snap.fx_rate_used : undefined
  const fxSource = snap && typeof snap.fx_source === 'string' ? snap.fx_source : undefined
  const fxAsOf = snap && typeof snap.fx_as_of === 'string' ? snap.fx_as_of : undefined
  const responseCost = snap && typeof snap.response_cost === 'number' ? snap.response_cost : costUsd
  const meteringMode =
    snap && typeof snap.metering_mode === 'string' ? snap.metering_mode : undefined
  const billingPackage =
    snap && typeof snap.billing_package === 'string' ? snap.billing_package : undefined
  const shadowUpstream =
    snap && typeof snap.shadow_upstream_cost_usd === 'number' ? snap.shadow_upstream_cost_usd : null
  const hitChain = snap && Array.isArray(snap.hit_chain) ? (snap.hit_chain as string[]) : null
  const isPackageMetering = meteringMode === 'package' || Boolean(billingPackage)

  return (
    <section className="space-y-2 rounded-md border bg-muted/20 p-3">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        计费拆解
      </h3>
      {isPackageMetering ? (
        <p className="text-xs text-amber-700 dark:text-amber-400">
          套餐/包量调用：按量费用为 ¥0，额度在套餐或 Provider 计划中扣减。
          {billingPackage ? `（${billingPackage}）` : null}
        </p>
      ) : null}
      <dl className="grid grid-cols-[100px_1fr] gap-x-2 gap-y-1.5 text-xs">
        <dt className="text-muted-foreground">下游费用</dt>
        <dd className="tabular-nums">{formatMoneyDual(revenueUsd, currency, fxRate)}</dd>
        {isAdmin ? (
          <>
            <dt className="text-muted-foreground">上游成本</dt>
            <dd className="tabular-nums">{formatMoneyDual(costUsd, currency, fxRate)}</dd>
            {shadowUpstream !== null && costUsd === 0 ? (
              <>
                <dt className="text-muted-foreground">影子上游</dt>
                <dd className="tabular-nums text-muted-foreground">
                  {formatMoneyDual(shadowUpstream, currency, fxRate)}
                </dd>
              </>
            ) : null}
            <dt className="text-muted-foreground">毛利</dt>
            <dd className="tabular-nums">{formatMoneyDual(marginUsd, currency, fxRate)}</dd>
          </>
        ) : null}
        {isAdmin && hitChain && hitChain.length > 0 ? (
          <>
            <dt className="text-muted-foreground">命中链</dt>
            <dd className="font-mono text-[11px]">{hitChain.join(' → ')}</dd>
          </>
        ) : null}
        {snap?.custom_pricing !== undefined && snap.custom_pricing !== null ? (
          <>
            <dt className="text-muted-foreground">自定义价</dt>
            <dd className="font-mono text-[11px]">
              {formatPricingSnapshotValue(snap.custom_pricing)}
            </dd>
          </>
        ) : null}
        {responseCost !== costUsd ? (
          <>
            <dt className="text-muted-foreground">LiteLLM cost</dt>
            <dd className="tabular-nums">${responseCost.toFixed(6)}</dd>
          </>
        ) : null}
        {fxRate ? (
          <>
            <dt className="text-muted-foreground">汇率</dt>
            <dd>
              1 USD = {fxRate} CNY
              {fxSource ? ` (${fxSource}${fxAsOf ? ` · ${fxAsOf}` : ''})` : null}
            </dd>
          </>
        ) : null}
      </dl>
      {isAdmin ? (
        <p className="text-[11px] text-muted-foreground">
          完整定价快照见下方 JSON；可在{' '}
          <Link
            to="/gateway/pricing/upstream"
            className="text-primary underline-offset-4 hover:underline"
          >
            上游定价
          </Link>{' '}
          维护成本目录。
        </p>
      ) : null}
    </section>
  )
}

function formatPricingSnapshotValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') {
    return String(value)
  }
  return JSON.stringify(value)
}

function formatMoneyDual(usd: number, currency: DisplayCurrency, fxRate?: string): string {
  const usdStr = formatMoney(usd, { currency: 'USD', precision: 6 })
  if (currency === 'USD') return usdStr
  const rate = fxRate ? Number(fxRate) : 7.2
  const cny = Number.isFinite(rate) ? usd * rate : usd
  return `${formatMoney(cny, { currency: 'CNY' })} (${usdStr})`
}
