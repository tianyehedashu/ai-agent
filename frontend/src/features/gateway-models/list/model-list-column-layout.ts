/** 统一模型列表可调整列宽布局（px + localStorage 持久化）。 */

export const MODEL_LIST_COLUMN_KEYS = [
  'affiliation',
  'invokeName',
  'displayName',
  'channel',
  'upstream',
  'capability',
  'credential',
  'status',
] as const

export type ModelListColumnKey = (typeof MODEL_LIST_COLUMN_KEYS)[number]

export type ModelListColumnWidths = Record<ModelListColumnKey, number>

export const DEFAULT_MODEL_LIST_COLUMN_WIDTHS: ModelListColumnWidths = {
  affiliation: 152,
  invokeName: 196,
  displayName: 136,
  channel: 104,
  upstream: 148,
  capability: 112,
  credential: 136,
  status: 92,
}

export const MIN_MODEL_LIST_COLUMN_WIDTHS: ModelListColumnWidths = {
  affiliation: 72,
  invokeName: 100,
  displayName: 72,
  channel: 72,
  upstream: 96,
  capability: 72,
  credential: 80,
  status: 72,
}

const BATCH_SELECT_COLUMN_PX = 40
const TRAILING_COLUMN_MIN_PX = 108

export interface ModelListGridOptions {
  showBatchSelect: boolean
  showTrailing: boolean
  showAffiliationColumn?: boolean
}

export function buildModelListGridTemplateColumns(
  widths: ModelListColumnWidths,
  options: ModelListGridOptions
): string {
  const parts: string[] = []
  if (options.showBatchSelect) {
    parts.push(`${String(BATCH_SELECT_COLUMN_PX)}px`)
  }
  const showAffiliation = options.showAffiliationColumn !== false
  for (const key of MODEL_LIST_COLUMN_KEYS) {
    if (key === 'affiliation' && !showAffiliation) continue
    parts.push(`${String(widths[key])}px`)
  }
  if (options.showTrailing) {
    parts.push(`minmax(${String(TRAILING_COLUMN_MIN_PX)}px, auto)`)
  }
  return parts.join(' ')
}

export function computeModelListTableMinWidth(
  widths: ModelListColumnWidths,
  options: ModelListGridOptions
): number {
  const showAffiliation = options.showAffiliationColumn !== false
  let total = MODEL_LIST_COLUMN_KEYS.reduce((sum, key) => {
    if (key === 'affiliation' && !showAffiliation) return sum
    return sum + widths[key]
  }, 0)
  if (options.showBatchSelect) total += BATCH_SELECT_COLUMN_PX
  if (options.showTrailing) total += TRAILING_COLUMN_MIN_PX
  return total
}

export function clampModelListColumnWidth(key: ModelListColumnKey, width: number): number {
  return Math.max(MIN_MODEL_LIST_COLUMN_WIDTHS[key], Math.round(width))
}
