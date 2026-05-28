export function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

export function formatCompact(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(2)}K`
  return Math.round(value).toLocaleString()
}
