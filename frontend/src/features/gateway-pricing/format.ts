import { formatMoney, formatRatePerMillion } from '@/lib/money'
import type { DisplayCurrency, MoneyDisplay } from '@/types/money'

export function formatRateLine(
  input: MoneyDisplay | null | undefined,
  output: MoneyDisplay | null | undefined,
  _currency: DisplayCurrency
): string {
  if (input && output) {
    return `${formatRatePerMillion(input, 'in')} · ${formatRatePerMillion(output, 'out')}`
  }
  return '跟随上游'
}

export function formatMoneyFromDisplay(
  display: MoneyDisplay | null | undefined,
  _fallbackCurrency: DisplayCurrency
): string {
  if (!display) return '—'
  return formatMoney(display.amount, { currency: display.currency })
}
