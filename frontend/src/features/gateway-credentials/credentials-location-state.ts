import type { CredentialsListTab } from '@/features/gateway-models/paths'

export interface CredentialsLocationState {
  credentialsTab?: CredentialsListTab
}

export function resolveCredentialsListTab(
  searchTab: string | null,
  locationState: CredentialsLocationState | null | undefined,
  credScope?: 'user' | 'team' | 'system'
): CredentialsListTab {
  if (locationState?.credentialsTab) {
    return locationState.credentialsTab
  }
  if (searchTab === 'personal' || searchTab === 'shared' || searchTab === 'system') {
    return searchTab
  }
  if (credScope === 'system') return 'system'
  if (credScope === 'user') return 'personal'
  return 'shared'
}
