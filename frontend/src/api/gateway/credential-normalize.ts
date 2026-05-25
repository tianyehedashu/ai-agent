export type NormalizedCredentialScope = 'system' | 'team' | 'user'

export interface NormalizedProviderCredential {
  id: string
  tenant_id: string | null
  scope: NormalizedCredentialScope
  scope_id: string | null
  provider: string
  name: string
  api_base: string | null
  is_active: boolean
  is_config_managed?: boolean
  visibility?: 'public' | 'restricted' | null
  extra: Record<string, unknown> | null
  created_at: string
  api_key_masked: string
}
export interface ProviderCredentialWire {
  id: string
  tenant_id?: string | null
  scope: 'system' | 'team' | 'user' | null
  scope_id: string | null
  provider: string
  name: string
  api_base: string | null
  is_active: boolean
  is_config_managed?: boolean
  visibility?: 'public' | 'restricted' | null
  extra: Record<string, unknown> | null
  created_at: string
  api_key_masked: string
}

export function normalizeCredentialScope(
  scope: ProviderCredentialWire['scope'],
  tenantId: string | null | undefined
): NormalizedCredentialScope {
  if (scope === 'system' || scope === 'user') return scope
  if (scope === 'team' || (tenantId !== null && tenantId !== undefined)) return 'team'
  return 'user'
}

export function normalizeCredential(raw: ProviderCredentialWire): NormalizedProviderCredential {
  const tenant_id = raw.tenant_id ?? null
  return {
    id: raw.id,
    tenant_id,
    scope: normalizeCredentialScope(raw.scope, tenant_id),
    scope_id: raw.scope_id,
    provider: raw.provider,
    name: raw.name,
    api_base: raw.api_base,
    is_active: raw.is_active,
    is_config_managed: raw.is_config_managed,
    visibility: raw.visibility ?? null,
    extra: raw.extra,
    created_at: raw.created_at,
    api_key_masked: raw.api_key_masked,
  }
}
