import type { ProviderCredential } from '@/api/gateway'

import { CONFIG_MANAGED_BY, CONFIG_MANAGED_CREDENTIAL_NAME } from './constants'

function isConfigManagedFallback(c: ProviderCredential): boolean {
  if (c.scope !== 'system') return false
  if (c.extra?.managed_by === CONFIG_MANAGED_BY) return true
  return c.name === CONFIG_MANAGED_CREDENTIAL_NAME
}

export function isConfigManagedSystemCredential(c: ProviderCredential): boolean {
  return c.is_config_managed ?? isConfigManagedFallback(c)
}
