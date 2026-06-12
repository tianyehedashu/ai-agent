/**
 * 模型列表列宽 UI 偏好（localStorage）。
 */

import {
  clampModelListColumnWidth,
  DEFAULT_MODEL_LIST_COLUMN_WIDTHS,
  MODEL_LIST_COLUMN_KEYS,
  type ModelListColumnKey,
  type ModelListColumnWidths,
} from './model-list-column-layout'

const STORAGE_KEY = 'gateway-model-list-column-widths-v2'

export function loadModelListColumnWidths(): ModelListColumnWidths {
  if (typeof window === 'undefined') {
    return { ...DEFAULT_MODEL_LIST_COLUMN_WIDTHS }
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_MODEL_LIST_COLUMN_WIDTHS }
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) {
      return { ...DEFAULT_MODEL_LIST_COLUMN_WIDTHS }
    }
    const record = parsed as Record<string, unknown>
    const next = { ...DEFAULT_MODEL_LIST_COLUMN_WIDTHS }
    for (const key of MODEL_LIST_COLUMN_KEYS) {
      const value = record[key]
      if (typeof value === 'number' && Number.isFinite(value)) {
        next[key] = clampModelListColumnWidth(key, value)
      }
    }
    return next
  } catch {
    return { ...DEFAULT_MODEL_LIST_COLUMN_WIDTHS }
  }
}

export function saveModelListColumnWidths(widths: ModelListColumnWidths): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(widths))
  } catch {
    // ignore quota / private mode
  }
}

export function resetModelListColumnWidth(
  widths: ModelListColumnWidths,
  key: ModelListColumnKey
): ModelListColumnWidths {
  return { ...widths, [key]: DEFAULT_MODEL_LIST_COLUMN_WIDTHS[key] }
}
