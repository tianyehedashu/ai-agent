import {
  clampQuotaCenterColumnWidth,
  DEFAULT_QUOTA_CENTER_COLUMN_WIDTHS,
  QUOTA_CENTER_COLUMN_KEYS,
  type QuotaCenterColumnKey,
  type QuotaCenterColumnWidths,
} from './quota-center-column-layout'

const STORAGE_KEY = 'gateway-quota-center-column-widths-v1'

export function loadQuotaCenterColumnWidths(): QuotaCenterColumnWidths {
  if (typeof window === 'undefined') {
    return { ...DEFAULT_QUOTA_CENTER_COLUMN_WIDTHS }
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_QUOTA_CENTER_COLUMN_WIDTHS }
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) {
      return { ...DEFAULT_QUOTA_CENTER_COLUMN_WIDTHS }
    }
    const record = parsed as Record<string, unknown>
    const next = { ...DEFAULT_QUOTA_CENTER_COLUMN_WIDTHS }
    for (const key of QUOTA_CENTER_COLUMN_KEYS) {
      const value = record[key]
      if (typeof value === 'number' && Number.isFinite(value)) {
        next[key] = clampQuotaCenterColumnWidth(key, value)
      }
    }
    return next
  } catch {
    return { ...DEFAULT_QUOTA_CENTER_COLUMN_WIDTHS }
  }
}

export function saveQuotaCenterColumnWidths(widths: QuotaCenterColumnWidths): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(widths))
  } catch {
    // ignore quota / private mode
  }
}

export function resetQuotaCenterColumnWidth(
  widths: QuotaCenterColumnWidths,
  key: QuotaCenterColumnKey
): QuotaCenterColumnWidths {
  return { ...widths, [key]: DEFAULT_QUOTA_CENTER_COLUMN_WIDTHS[key] }
}
