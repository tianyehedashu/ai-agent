export type DateRangeValue = '1h' | 'today' | '7d' | '30d'

export function resolveDateRange(value: DateRangeValue): { start: Date; end: Date } {
  const end = new Date()
  const start = new Date(end)
  if (value === '1h') {
    start.setHours(start.getHours() - 1)
  } else if (value === 'today') {
    start.setHours(0, 0, 0, 0)
  } else if (value === '7d') {
    start.setDate(start.getDate() - 7)
  } else {
    // '30d'
    start.setDate(start.getDate() - 30)
  }
  return { start, end }
}

export function isValidDateRangeValue(value: string | null): value is DateRangeValue {
  return value === '1h' || value === 'today' || value === '7d' || value === '30d'
}
