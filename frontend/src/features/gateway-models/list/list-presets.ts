import type { GatewayModelListCapabilities } from './types'

/** 三个可写 Tab 共享的全量能力（差异仅来自权限 gate） */
export const SHARED_FULL = {
  search: true,
  credentialFilter: true,
  channelFilter: true,
  abilityFilter: true,
  healthFilter: true,
  credentialBanner: true,
  modelIdHighlight: true,
  channelHint: true,
  usageSummary: true,
  batchSelect: true,
  batchBarMode: 'onSelection',
  batchTest: true,
  batchResync: true,
  batchDelete: true,
  deleteAllFiltered: true,
  deleteFailed: true,
  rowToggleEnabled: true,
  rowDelete: true,
  rowNavigation: true,
  connectivityBanner: true,
  layout: 'compact',
  connectivityDisplay: 'attention-only',
} as const satisfies Omit<GatewayModelListCapabilities, 'scope'>

export const PERSONAL_LIST_CAPABILITIES: GatewayModelListCapabilities = {
  ...SHARED_FULL,
  scope: 'personal',
  deleteAllFilteredFetcher: 'personal',
}

export const TEAM_GROUPED_CAPABILITIES: GatewayModelListCapabilities = {
  ...SHARED_FULL,
  scope: 'team',
  groupedByTeam: true,
  teamSearch: true,
  dualSearchStaleLoading: true,
  deleteAllFilteredFetcher: 'managed-teams',
}

export const SYSTEM_ADMIN_CAPABILITIES: GatewayModelListCapabilities = {
  ...SHARED_FULL,
  scope: 'system',
  showSystemAdmin: true,
  deleteAllFilteredFetcher: 'single-team',
}

export const SYSTEM_BROWSE_CAPABILITIES: GatewayModelListCapabilities = {
  scope: 'system',
  variant: 'readonly',
  search: true,
  channelFilter: true,
  abilityFilter: true,
  layout: 'compact',
  connectivityDisplay: 'attention-only',
  headerSlot: true,
}

export const EMBEDDED_CREDENTIAL_CAPABILITIES: GatewayModelListCapabilities = {
  scope: 'team',
  variant: 'embedded',
  layout: 'compact',
  connectivityDisplay: 'attention-only',
  rowNavigation: true,
}
