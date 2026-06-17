/** 配额中心列表 grid 列宽（表头与行共用同一模板，localStorage 持久化）。 */

export const QUOTA_CENTER_COLUMN_KEYS = [
  'layer',
  'subject',
  'credential',
  'invokeName',
  'upstream',
  'period',
  'usage',
  'usageRatio',
  'source',
] as const

export type QuotaCenterColumnKey = (typeof QUOTA_CENTER_COLUMN_KEYS)[number]

export type QuotaCenterColumnWidths = Record<QuotaCenterColumnKey, number>

export const DEFAULT_QUOTA_CENTER_COLUMN_WIDTHS: QuotaCenterColumnWidths = {
  layer: 88,
  subject: 112,
  credential: 120,
  invokeName: 200,
  upstream: 148,
  period: 128,
  usage: 160,
  usageRatio: 120,
  source: 96,
}

export const MIN_QUOTA_CENTER_COLUMN_WIDTHS: QuotaCenterColumnWidths = {
  layer: 72,
  subject: 80,
  credential: 80,
  invokeName: 120,
  upstream: 96,
  period: 96,
  usage: 120,
  usageRatio: 96,
  source: 72,
}

const CHECKBOX_COLUMN_PX = 40
const ACTIONS_COLUMN_MIN_PX = 132

export function clampQuotaCenterColumnWidth(key: QuotaCenterColumnKey, width: number): number {
  return Math.max(MIN_QUOTA_CENTER_COLUMN_WIDTHS[key], Math.round(width))
}

export function buildQuotaCenterGridTemplateColumns(
  widths: QuotaCenterColumnWidths = DEFAULT_QUOTA_CENTER_COLUMN_WIDTHS
): string {
  const parts = [
    `${String(CHECKBOX_COLUMN_PX)}px`,
    ...QUOTA_CENTER_COLUMN_KEYS.map((key) => `${String(widths[key])}px`),
    `minmax(${String(ACTIONS_COLUMN_MIN_PX)}px, auto)`,
  ]
  return parts.join(' ')
}

export function computeQuotaCenterTableMinWidth(
  widths: QuotaCenterColumnWidths = DEFAULT_QUOTA_CENTER_COLUMN_WIDTHS
): number {
  let total = CHECKBOX_COLUMN_PX + ACTIONS_COLUMN_MIN_PX
  for (const key of QUOTA_CENTER_COLUMN_KEYS) {
    total += widths[key]
  }
  return total
}
