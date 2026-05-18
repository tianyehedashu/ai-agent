/**
 * 凭据 extra 字段相关的纯函数（不依赖 React），便于 HMR 与单测。
 */

export type CredentialExtraValues = Record<string, string>

/** 仅保留非空字段；空字符串视为「未填」，避免覆盖后端旧值时把字段擦成空串。 */
export function compactExtra(values: CredentialExtraValues): Record<string, string> {
  const out: Record<string, string> = {}
  for (const [k, v] of Object.entries(values)) {
    const trimmed = v.trim()
    if (trimmed) out[k] = trimmed
  }
  return out
}

/** 把已存的 extra 转换成表单 state（只读 string）。 */
export function extraToFormValues(
  extra: Record<string, unknown> | null | undefined
): CredentialExtraValues {
  if (!extra) return {}
  const out: CredentialExtraValues = {}
  for (const [k, v] of Object.entries(extra)) {
    if (v === null || v === undefined) continue
    out[k] = typeof v === 'string' ? v : JSON.stringify(v)
  }
  return out
}
