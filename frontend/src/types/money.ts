/** 与后端 MoneyDisplay schema 对齐 */

export type DisplayCurrency = 'CNY' | 'USD'

export interface MoneyDisplay {
  amount: string
  currency: DisplayCurrency
  fx_rate_used: string
}
