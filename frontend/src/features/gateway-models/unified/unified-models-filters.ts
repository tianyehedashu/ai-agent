/**
 * 统一模型列表：筛选与分页（纯函数）。
 */

import type { GatewayModel } from '@/api/gateway/models'
import type { PersonalGatewayModel } from '@/api/gateway/my-models'
import { credentialTeamLabel } from '@/features/gateway-credentials/credential-scope-labels'
import type { HealthFilter } from '@/features/gateway-models/constants'
import { channelLabel } from '@/features/gateway-models/utils'
import { DEFAULT_PAGE_SIZE } from '@/lib/pagination'

import { resolveModelListDisplayLabel } from '../list/gateway-model-display-name'

import type { GatewayModelListItem, GatewayModelListScope } from '../list/types'

export type UnifiedModelScopeFilter = 'all' | GatewayModelListScope

export interface UnifiedModelsScopeCounts {
  personal: number
  team: number
  system: number
  total: number
}

export interface UnifiedModelsPaginationSlice {
  items: readonly GatewayModelListItem[]
  page: number
  page_size: number
  total: number
  has_next: boolean
  has_prev: boolean
}

export function matchesModelScopeFilter(
  item: GatewayModelListItem,
  scopeFilter: UnifiedModelScopeFilter
): boolean {
  if (scopeFilter === 'all') return true
  return item.scope === scopeFilter
}

export function affiliationLabelForModel(
  item: GatewayModelListItem,
  teamNameById: Map<string, string>
): string {
  if (item.scope === 'personal') return '个人'
  if (item.scope === 'system') return '系统'
  return credentialTeamLabel(item.teamId, teamNameById)
}

export interface UnifiedModelsFilterOptions {
  search: string
  scopeFilter: UnifiedModelScopeFilter
  teamNameById: Map<string, string>
  providerFilter?: string
  healthFilter?: HealthFilter
  credentialFilter?: string
  /** 按归属团队 ID 精确筛选（个人模型无 teamId，不会匹配） */
  teamFilter?: string
}

export function modelCredentialId(item: GatewayModelListItem): string | null {
  if (item.credentialId) return item.credentialId
  if (item.scope === 'personal') {
    return (item.source as PersonalGatewayModel).credential_id
  }
  return (item.source as GatewayModel).credential_id
}

export function matchesProviderFilter(item: GatewayModelListItem, providerFilter: string): boolean {
  if (!providerFilter) return true
  return item.provider === providerFilter
}

export function matchesHealthFilter(
  item: GatewayModelListItem,
  healthFilter: HealthFilter
): boolean {
  if (healthFilter === 'all') return true
  if (healthFilter === 'unknown') return item.lastTestStatus === null
  return item.lastTestStatus === healthFilter
}

export function matchesCredentialFilter(
  item: GatewayModelListItem,
  credentialFilter: string
): boolean {
  if (!credentialFilter) return true
  return modelCredentialId(item) === credentialFilter
}

export function shouldShowUnifiedAffiliationColumn(
  scopeFilter: UnifiedModelScopeFilter,
  teamFilter: string
): boolean {
  if (scopeFilter === 'personal' || scopeFilter === 'system') return false
  if (teamFilter !== '') return false
  return true
}

export function shouldShowUnifiedTeamFilter(
  scopeFilter: UnifiedModelScopeFilter,
  teamsWithModelsCount: number
): boolean {
  if (teamsWithModelsCount < 2) return false
  return scopeFilter === 'all' || scopeFilter === 'team'
}

export function matchesTeamFilter(item: GatewayModelListItem, teamFilter: string): boolean {
  if (!teamFilter) return true
  return item.teamId === teamFilter
}

export function summarizeUnifiedModelsHealth(items: readonly GatewayModelListItem[]): {
  total: number
  success: number
  failed: number
  unknown: number
} {
  let success = 0
  let failed = 0
  let unknown = 0
  for (const item of items) {
    if (item.lastTestStatus === 'success') success += 1
    else if (item.lastTestStatus === 'failed') failed += 1
    else unknown += 1
  }
  return { total: items.length, success, failed, unknown }
}

export function matchesModelSearch(
  item: GatewayModelListItem,
  search: string,
  teamNameById: Map<string, string>
): boolean {
  const q = search.trim().toLowerCase()
  if (!q) return true

  const affiliation = affiliationLabelForModel(item, teamNameById)
  const displayLabel = resolveModelListDisplayLabel(item)
  return (
    item.title.toLowerCase().includes(q) ||
    (displayLabel?.toLowerCase().includes(q) ?? false) ||
    item.subtitle.toLowerCase().includes(q) ||
    item.upstreamModelId.toLowerCase().includes(q) ||
    item.provider.toLowerCase().includes(q) ||
    channelLabel(item.provider).toLowerCase().includes(q) ||
    affiliation.toLowerCase().includes(q) ||
    (item.routeName?.toLowerCase().includes(q) ?? false)
  )
}

function scopeSortRank(scope: GatewayModelListScope): number {
  if (scope === 'personal') return 0
  if (scope === 'team') return 1
  return 2
}

export function sortUnifiedModelEntries(
  items: readonly GatewayModelListItem[],
  teamNameById: Map<string, string>
): GatewayModelListItem[] {
  return [...items].sort((a, b) => {
    const scopeDiff = scopeSortRank(a.scope) - scopeSortRank(b.scope)
    if (scopeDiff !== 0) return scopeDiff

    if (a.scope === 'team' && b.scope === 'team') {
      const teamA = affiliationLabelForModel(a, teamNameById)
      const teamB = affiliationLabelForModel(b, teamNameById)
      const teamDiff = teamA.localeCompare(teamB, 'zh-CN')
      if (teamDiff !== 0) return teamDiff
    }

    return a.title.localeCompare(b.title, 'zh-CN')
  })
}

export function countUnifiedModelsByScope(
  items: readonly GatewayModelListItem[]
): UnifiedModelsScopeCounts {
  let personal = 0
  let team = 0
  let system = 0
  for (const item of items) {
    if (item.scope === 'personal') personal += 1
    else if (item.scope === 'team') team += 1
    else system += 1
  }
  return { personal, team, system, total: items.length }
}

export function filterUnifiedModelEntries(
  items: readonly GatewayModelListItem[],
  options: UnifiedModelsFilterOptions
): GatewayModelListItem[] {
  const {
    search,
    scopeFilter,
    teamNameById,
    providerFilter = '',
    healthFilter = 'all',
    credentialFilter = '',
    teamFilter = '',
  } = options
  const filtered = items.filter(
    (item) =>
      matchesModelScopeFilter(item, scopeFilter) &&
      matchesTeamFilter(item, teamFilter) &&
      matchesModelSearch(item, search, teamNameById) &&
      matchesProviderFilter(item, providerFilter) &&
      matchesHealthFilter(item, healthFilter) &&
      matchesCredentialFilter(item, credentialFilter)
  )
  return sortUnifiedModelEntries(filtered, teamNameById)
}

export function paginateUnifiedModelEntries(
  items: readonly GatewayModelListItem[],
  page: number,
  pageSize: number = DEFAULT_PAGE_SIZE
): UnifiedModelsPaginationSlice {
  const total = items.length
  const page_size = pageSize
  const totalPages = Math.max(1, Math.ceil(total / page_size))
  const safePage = Math.min(Math.max(1, page), totalPages)
  const start = (safePage - 1) * page_size
  const slice = items.slice(start, start + page_size)
  return {
    items: slice,
    page: safePage,
    page_size,
    total,
    has_next: safePage < totalPages,
    has_prev: safePage > 1,
  }
}
