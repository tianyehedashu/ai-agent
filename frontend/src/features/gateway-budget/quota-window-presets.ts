export const QUOTA_WINDOW_PRESETS = [
  { value: '0', label: '套餐周期' },
  { value: '86400', label: '每日' },
  { value: '2592000', label: '每月' },
  { value: 'custom', label: '自定义秒数' },
] as const

export type QuotaWindowPresetValue = (typeof QUOTA_WINDOW_PRESETS)[number]['value']

export function resolveQuotaWindowPreset(windowSeconds: string): QuotaWindowPresetValue {
  const v = windowSeconds.trim()
  if (v === '0') return '0'
  if (v === '86400') return '86400'
  if (v === '2592000') return '2592000'
  return 'custom'
}

export function applyQuotaWindowPreset(
  preset: QuotaWindowPresetValue,
  currentWindowSeconds: string
): string {
  if (preset === 'custom') return currentWindowSeconds.trim() || ''
  return preset
}

/** 每日/每月预设对应上游 reset_strategy（写路径透传） */
export function resetStrategyForWindowPreset(
  windowSeconds: string
): 'calendar_daily_utc' | 'calendar_monthly_utc' | null {
  const v = windowSeconds.trim()
  if (v === '86400') return 'calendar_daily_utc'
  if (v === '2592000') return 'calendar_monthly_utc'
  return null
}
