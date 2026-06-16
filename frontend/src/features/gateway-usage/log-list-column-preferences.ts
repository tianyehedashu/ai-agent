/**
 * 调用日志列表列宽 UI 偏好（localStorage）。
 */

import {
  clampLogListColumnWidth,
  DEFAULT_LOG_LIST_COLUMN_WIDTHS,
  LOG_LIST_COLUMN_KEYS,
  type LogListColumnWidths,
  type LogListColumnKey,
} from '@/features/gateway-usage/log-list-column-layout'

const STORAGE_KEY = 'gateway-log-list-column-widths-v1'

export function loadLogListColumnWidths(): LogListColumnWidths {
  if (typeof window === 'undefined') {
    return { ...DEFAULT_LOG_LIST_COLUMN_WIDTHS }
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_LOG_LIST_COLUMN_WIDTHS }
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) {
      return { ...DEFAULT_LOG_LIST_COLUMN_WIDTHS }
    }
    const record = parsed as Record<string, unknown>
    const next = { ...DEFAULT_LOG_LIST_COLUMN_WIDTHS }
    for (const key of LOG_LIST_COLUMN_KEYS) {
      const value = record[key]
      if (typeof value === 'number' && Number.isFinite(value)) {
        next[key] = clampLogListColumnWidth(key, value)
      }
    }
    return next
  } catch {
    return { ...DEFAULT_LOG_LIST_COLUMN_WIDTHS }
  }
}

export function saveLogListColumnWidths(widths: LogListColumnWidths): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(widths))
  } catch {
    // ignore quota / private mode
  }
}

export function resetLogListColumnWidth(
  widths: LogListColumnWidths,
  key: LogListColumnKey
): LogListColumnWidths {
  return { ...widths, [key]: DEFAULT_LOG_LIST_COLUMN_WIDTHS[key] }
}
