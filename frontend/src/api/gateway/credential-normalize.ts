export type NormalizedCredentialScope = 'system' | 'team' | 'user'

export interface CredentialApiBases {
  openai_compat?: string | null
  anthropic_native?: string | null
}

export interface NormalizedProviderCredential {
  id: string
  tenant_id: string | null
  scope: NormalizedCredentialScope
  scope_id: string | null
  provider: string
  name: string
  api_base: string | null
  api_bases?: CredentialApiBases | null
  profile_id?: string | null
  profile_label?: string | null
  effective_api_base_openai?: string | null
  effective_api_base_anthropic?: string | null
  is_active: boolean
  is_config_managed?: boolean
  visibility?: 'public' | 'restricted' | null
  extra: Record<string, unknown> | null
  created_at: string
  api_key_masked: string
  created_by_user_id?: string | null
  created_by_label?: string | null
  management_access?: 'full' | 'metadata'
}
export interface ProviderCredentialWire {
  id: string
  tenant_id?: string | null
  scope: 'system' | 'team' | 'user' | null
  scope_id: string | null
  provider: string
  name: string
  api_base: string | null
  api_bases?: CredentialApiBases | null
  profile_id?: string | null
  profile_label?: string | null
  effective_api_base_openai?: string | null
  effective_api_base_anthropic?: string | null
  is_active: boolean
  is_config_managed?: boolean
  visibility?: 'public' | 'restricted' | null
  extra: Record<string, unknown> | null
  created_at: string
  api_key_masked: string
  created_by_user_id?: string | null
  created_by_label?: string | null
  management_access?: 'full' | 'metadata'
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
    api_bases: raw.api_bases ?? null,
    profile_id: raw.profile_id ?? null,
    profile_label: raw.profile_label ?? null,
    effective_api_base_openai: raw.effective_api_base_openai ?? null,
    effective_api_base_anthropic: raw.effective_api_base_anthropic ?? null,
    is_active: raw.is_active,
    is_config_managed: raw.is_config_managed,
    visibility: raw.visibility ?? null,
    extra: raw.extra,
    created_at: raw.created_at,
    api_key_masked: raw.api_key_masked,
    created_by_user_id: raw.created_by_user_id ?? null,
    created_by_label: raw.created_by_label ?? null,
    management_access: raw.management_access,
  }
}
