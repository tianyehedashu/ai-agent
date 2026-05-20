/**
 * 金额格式化（默认 CNY 展示，底层 USD 由 API 折算）
 */

import type { DisplayCurrency } from '@/types/money'

export interface FormatMoneyOptions {
  currency?: DisplayCurrency
  precision?: number
  unit?: '1K' | '1M'
  locale?: string
}

export function coalesceMoney(value: unknown): number {
  if (value === null || value === undefined || value === '') {
    return 0
  }
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : 0
  }
  if (typeof value === 'string') {
    const n = Number(value)
    return Number.isFinite(n) ? n : 0
  }
  return 0
}

export function formatMoney(amount: unknown, options: FormatMoneyOptions = {}): string {
  const currency = options.currency ?? 'CNY'
  const precision = options.precision ?? (currency === 'CNY' ? 2 : 4)
  const locale = options.locale ?? (currency === 'CNY' ? 'zh-CN' : 'en-US')
  let n = coalesceMoney(amount)
  if (options.unit === '1M') {
    n *= 1_000_000
  } else if (options.unit === '1K') {
    n *= 1_000
  }
  if (currency === 'CNY' && n > 0 && n < 0.01) {
    return `¥${n.toLocaleString(locale, { minimumFractionDigits: 4, maximumFractionDigits: 6 })}`
  }
  const prefix = currency === 'CNY' ? '¥' : '$'
  return `${prefix}${n.toLocaleString(locale, { minimumFractionDigits: precision, maximumFractionDigits: precision })}`
}

export function formatRatePerMillion(
  display: { amount: string; currency: DisplayCurrency } | null | undefined,
  side: 'in' | 'out'
): string {
  if (!display) {
    return '—'
  }
  const label = side === 'in' ? 'in' : 'out'
  return `${formatMoney(display.amount, { currency: display.currency })} / 1M ${label}`
}
