export const QUOTA_TOKENS_PER_WAN = 10_000

/** 表单：原始 token 数 → 万 单位输入框字符串 */
export function tokensToWanInput(raw: string): string {
  const trimmed = raw.trim()
  if (!trimmed) return ''
  const n = Number(trimmed)
  if (!Number.isFinite(n)) return trimmed
  if (n === 0) return '0'
  const wan = n / QUOTA_TOKENS_PER_WAN
  return Number.isInteger(wan) ? String(wan) : wan.toFixed(4).replace(/\.?0+$/, '')
}

/** 表单：万 单位输入 → 原始 token 数字符串（空则 ''） */
export function wanInputToTokenString(wan: string): string {
  const trimmed = wan.trim()
  if (!trimmed) return ''
  const n = Number(trimmed)
  if (!Number.isFinite(n) || n < 0) return ''
  return String(Math.round(n * QUOTA_TOKENS_PER_WAN))
}

/** 列表/摘要：展示 token 用量或限额（万） */
export function formatQuotaTokens(value: number | string | null | undefined): string {
  if (value === null || value === undefined) return '∞'
  const n = typeof value === 'string' ? Number(value) : value
  if (!Number.isFinite(n)) return String(value)
  if (n === 0) return '0'
  const wan = n / QUOTA_TOKENS_PER_WAN
  const text = Number.isInteger(wan) ? String(wan) : wan.toFixed(2).replace(/\.?0+$/, '')
  return `${text} 万`
}
