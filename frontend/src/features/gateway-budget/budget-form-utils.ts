export function parseOptionalInt(raw: string): number | null {
  const t = raw.trim()
  if (t === '') return null
  const n = Number.parseInt(t, 10)
  return Number.isFinite(n) && n >= 0 ? n : null
}

export function parseOptionalUsd(raw: string): number | null {
  const t = raw.trim()
  if (t === '') return null
  const n = Number.parseFloat(t)
  return Number.isFinite(n) && n >= 0 ? n : null
}
