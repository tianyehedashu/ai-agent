/** 调用日志列表 grid 列宽（表头与行共用同一模板，localStorage 持久化）。 */

export interface LogListGridOptions {
  showCallerColumn: boolean
}

export const LOG_LIST_COLUMN_KEYS = [
  'time',
  'caller',
  'invokeName',
  'upstream',
  'credential',
  'capability',
  'status',
  'tokens',
  'cost',
  'latency',
  'ttfb',
  'requestId',
] as const

export type LogListColumnKey = (typeof LOG_LIST_COLUMN_KEYS)[number]

export type LogListColumnWidths = Record<LogListColumnKey, number>

export const DEFAULT_LOG_LIST_COLUMN_WIDTHS: LogListColumnWidths = {
  time: 152,
  caller: 120,
  invokeName: 220,
  upstream: 128,
  credential: 120,
  capability: 96,
  status: 96,
  tokens: 88,
  cost: 80,
  latency: 76,
  ttfb: 72,
  requestId: 160,
}

export const MIN_LOG_LIST_COLUMN_WIDTHS: LogListColumnWidths = {
  time: 100,
  caller: 72,
  invokeName: 120,
  upstream: 96,
  credential: 80,
  capability: 72,
  status: 72,
  tokens: 64,
  cost: 64,
  latency: 64,
  ttfb: 64,
  requestId: 120,
}

export function clampLogListColumnWidth(key: LogListColumnKey, width: number): number {
  return Math.max(MIN_LOG_LIST_COLUMN_WIDTHS[key], Math.round(width))
}

function isLogListColumnVisible(key: LogListColumnKey, options: LogListGridOptions): boolean {
  return key !== 'caller' || options.showCallerColumn
}

function logListColumnWidthPart(key: LogListColumnKey, widths: LogListColumnWidths): string {
  if (key === 'requestId') {
    return `minmax(${String(widths.requestId)}px, 1fr)`
  }
  return `${String(widths[key])}px`
}

export function buildLogGridTemplateColumns(
  options: LogListGridOptions,
  widths: LogListColumnWidths = DEFAULT_LOG_LIST_COLUMN_WIDTHS
): string {
  const parts: string[] = []
  for (const key of LOG_LIST_COLUMN_KEYS) {
    if (!isLogListColumnVisible(key, options)) continue
    parts.push(logListColumnWidthPart(key, widths))
  }
  return parts.join(' ')
}

export function computeLogTableMinWidth(
  options: LogListGridOptions,
  widths: LogListColumnWidths = DEFAULT_LOG_LIST_COLUMN_WIDTHS
): number {
  let total = 0
  for (const key of LOG_LIST_COLUMN_KEYS) {
    if (!isLogListColumnVisible(key, options)) continue
    total += widths[key]
  }
  return total
}
