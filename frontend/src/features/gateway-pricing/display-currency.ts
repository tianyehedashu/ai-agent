import type { DisplayCurrency } from '@/types/money'

/** 与后端 FxRatePort.default_display_currency 一致（网关下游计价、日志展示） */
export const GATEWAY_DISPLAY_CURRENCY: DisplayCurrency = 'CNY'
