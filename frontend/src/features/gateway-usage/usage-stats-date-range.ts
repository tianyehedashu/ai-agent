export type UsageStatsPresetDays = 1 | 7 | 30 | 90

export interface UsageStatsDateRangeSelection {
  presetDays: UsageStatsPresetDays | null
  startDate: string
  endDate: string
}

export interface UsageStatsDateRangeQuery {
  days?: UsageStatsPresetDays
  start?: string
  end?: string
}

const DATE_INPUT_RE = /^\d{4}-\d{2}-\d{2}$/

function pad2(value: number): string {
  return value.toString(10).padStart(2, '0')
}

export function toDateInputValue(date: Date): string {
  return `${String(date.getFullYear())}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`
}

function parseDateInputValue(value: string): Date | null {
  if (!DATE_INPUT_RE.test(value)) return null
  const [yearRaw, monthRaw, dayRaw] = value.split('-')
  const year = Number(yearRaw)
  const month = Number(monthRaw)
  const day = Number(dayRaw)
  const date = new Date(year, month - 1, day)
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
    return null
  }
  return date
}

function dateAtEndOfDay(value: string): Date | null {
  const date = parseDateInputValue(value)
  if (date === null) return null
  date.setHours(23, 59, 59, 999)
  return date
}

function addDays(date: Date, days: number): Date {
  const next = new Date(date)
  next.setDate(next.getDate() + days)
  return next
}

export function isValidDateInputValue(value: string): boolean {
  return parseDateInputValue(value) !== null
}

export function usageStatsPresetDateRange(
  presetDays: UsageStatsPresetDays,
  today = new Date()
): UsageStatsDateRangeSelection {
  const endDate = toDateInputValue(today)
  return {
    presetDays,
    startDate: toDateInputValue(addDays(today, -presetDays)),
    endDate,
  }
}

export function usageStatsDefaultDateRange(): UsageStatsDateRangeSelection {
  return usageStatsPresetDateRange(1)
}

export function usageStatsCustomDateRange(
  startDate: string,
  endDate: string
): UsageStatsDateRangeSelection {
  const fallback = toDateInputValue(new Date())
  const safeStart = isValidDateInputValue(startDate) ? startDate : fallback
  const safeEnd = isValidDateInputValue(endDate) ? endDate : safeStart
  if (safeStart > safeEnd) {
    return { presetDays: null, startDate: safeEnd, endDate: safeEnd }
  }
  return { presetDays: null, startDate: safeStart, endDate: safeEnd }
}

export function usageStatsDateRangeToQuery(
  selection: UsageStatsDateRangeSelection
): UsageStatsDateRangeQuery {
  if (selection.presetDays !== null) {
    return { days: selection.presetDays }
  }
  const start = parseDateInputValue(selection.startDate)
  const end = dateAtEndOfDay(selection.endDate)
  if (start === null || end === null) {
    return { days: 1 }
  }
  return {
    start: start.toISOString(),
    end: end.toISOString(),
  }
}

export function usageStatsDateRangeKey(selection: UsageStatsDateRangeSelection): string {
  const query = usageStatsDateRangeToQuery(selection)
  if (query.days !== undefined) return `days:${String(query.days)}`
  return `custom:${query.start ?? ''}:${query.end ?? ''}`
}
