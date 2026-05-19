import type { MyPriceRow } from '@/api/gateway'
import { coalesceMoney, formatMoney } from '@/lib/money'
import type { DisplayCurrency } from '@/types/money'

/** 根据下游单价（每百万 token）与 usage 估算本次费用（展示货币）。 */
export function estimateUsageCostDisplay(
  row: MyPriceRow | undefined,
  promptTokens: number | undefined,
  completionTokens: number | undefined,
  currency: DisplayCurrency
): string | null {
  if (!row) return null
  const inRate = row.input_cost_per_million_display
  const outRate = row.output_cost_per_million_display
  if (!inRate && !outRate) return null
  const pin = promptTokens ?? 0
  const pout = completionTokens ?? 0
  const inCost =
    inRate !== null && inRate !== undefined ? (coalesceMoney(inRate.amount) * pin) / 1_000_000 : 0
  const outCost =
    outRate !== null && outRate !== undefined
      ? (coalesceMoney(outRate.amount) * pout) / 1_000_000
      : 0
  const total = inCost + outCost
  if (total <= 0 && pin + pout === 0) return null
  const formatted = formatMoney(total, {
    currency: inRate?.currency ?? outRate?.currency ?? currency,
  })
  return `${formatted}（本地预估）`
}
