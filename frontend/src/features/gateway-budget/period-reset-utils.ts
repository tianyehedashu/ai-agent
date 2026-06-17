export const COMMON_PERIOD_TIMEZONES = [
  'UTC',
  'Asia/Shanghai',
  'Asia/Tokyo',
  'Europe/London',
  'America/Los_Angeles',
  'America/New_York',
] as const

export interface PeriodResetAnchorInput {
  period_timezone?: string | null
  period_reset_minutes?: number | null
  period_reset_day?: number | null
}

export function minutesToTimeString(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

export function timeStringToMinutes(value: string): number | null {
  const trimmed = value.trim()
  const match = /^(\d{1,2}):(\d{2})$/.exec(trimmed)
  if (!match) return null
  const h = Number(match[1])
  const m = Number(match[2])
  if (h < 0 || h > 23 || m < 0 || m > 59) return null
  return h * 60 + m
}

export function formatTimezoneLabel(tz: string): string {
  return tz.replace(/_/g, ' ')
}

export function formatPeriodResetLabel(
  anchor: PeriodResetAnchorInput,
  period: string | null
): string {
  const tz = anchor.period_timezone?.trim() ?? 'UTC'
  const minutes = anchor.period_reset_minutes ?? 0
  const time = minutesToTimeString(minutes)
  const day = anchor.period_reset_day ?? 1
  const tzLabel = formatTimezoneLabel(tz)

  if (period === 'daily') {
    return `每日 ${time} (${tzLabel})`
  }
  if (period === 'monthly') {
    const suffix = day === 31 ? '（短月按月末）' : ''
    return `每月 ${String(day)} 日 ${time} (${tzLabel})${suffix}`
  }
  return '—'
}

export function isCalendarPeriodResetVisible(input: {
  layer: 'platform' | 'upstream' | 'downstream'
  period?: string
  windowSeconds?: string
  resetStrategy?: string | null
}): boolean {
  if (input.layer === 'platform') {
    return input.period === 'daily' || input.period === 'monthly'
  }
  if (input.resetStrategy === 'rolling') return false
  const ws = input.windowSeconds?.trim()
  if (ws === '86400' || ws === '2592000') return true
  if (
    input.resetStrategy === 'calendar_daily_utc' ||
    input.resetStrategy === 'calendar_monthly_utc'
  ) {
    return true
  }
  return false
}

export function isMonthlyPeriodReset(input: {
  layer: 'platform' | 'upstream' | 'downstream'
  period?: string
  windowSeconds?: string
  resetStrategy?: string | null
}): boolean {
  if (input.layer === 'platform') return input.period === 'monthly'
  const ws = input.windowSeconds?.trim()
  if (ws === '2592000') return true
  return input.resetStrategy === 'calendar_monthly_utc'
}
