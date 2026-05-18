/** 凭据在日志/毛利等表格中的展示文案（与后端 resolve_margin_group_label 优先级对齐）。 */

export interface CredentialDisplayFields {
  credential_id?: string | null
  credential_name_snapshot?: string | null
}

export function credentialDisplayText(item: CredentialDisplayFields): string {
  const name = item.credential_name_snapshot?.trim()
  if (name) return name
  if (item.credential_id) return `${item.credential_id.slice(0, 8)}…`
  return '—'
}

export function credentialDisplayTitle(item: CredentialDisplayFields): string | undefined {
  const name = item.credential_name_snapshot?.trim()
  if (name && item.credential_id) {
    return `${name} · ${item.credential_id}`
  }
  return item.credential_id ?? item.credential_name_snapshot ?? undefined
}

/** 毛利分组行：label + 可选 group_key（悬停详情） */
export function marginGroupRowTitle(
  label: string,
  groupKey: string | null | undefined
): string | undefined {
  if (!groupKey) return undefined
  if (label === groupKey) return groupKey
  return `${label} · ${groupKey}`
}
