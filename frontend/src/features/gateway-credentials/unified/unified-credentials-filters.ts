/**
 * 统一凭据列表：筛选与分页（纯函数）。
 */

import type { CredentialSummary, ProviderCredential } from '@/api/gateway'
import { credentialProviderLabel } from '@/features/gateway-credentials/credential-provider-display'
import { credentialTeamLabel } from '@/features/gateway-credentials/credential-scope-labels'
import { providerLabel } from '@/features/gateway-credentials/provider-schemas'
import { DEFAULT_PAGE_SIZE } from '@/lib/pagination'

export type UnifiedCredentialEntry =
  | { kind: 'full'; credential: ProviderCredential }
  | { kind: 'summary'; summary: CredentialSummary }

export type UnifiedCredentialScopeFilter = 'all' | 'user' | 'team' | 'system'

export interface UnifiedCredentialsScopeCounts {
  personal: number
  team: number
  system: number
  total: number
}

export interface UnifiedCredentialsPaginationSlice {
  items: readonly UnifiedCredentialEntry[]
  page: number
  page_size: number
  total: number
  has_next: boolean
  has_prev: boolean
}

export function entryScope(
  entry: UnifiedCredentialEntry
): ProviderCredential['scope'] | CredentialSummary['scope'] {
  return entry.kind === 'full' ? entry.credential.scope : entry.summary.scope
}

export function affiliationLabel(
  entry: UnifiedCredentialEntry,
  teamNameById: Map<string, string>
): string {
  const scope = entryScope(entry)
  if (scope === 'user') return '个人'
  if (scope === 'system') return '系统'
  if (entry.kind === 'full') {
    return credentialTeamLabel(entry.credential.tenant_id, teamNameById)
  }
  return '—'
}

export function matchesScopeFilter(
  entry: UnifiedCredentialEntry,
  scopeFilter: UnifiedCredentialScopeFilter
): boolean {
  if (scopeFilter === 'all') return true
  return entryScope(entry) === scopeFilter
}

export function matchesCredentialSearch(
  entry: UnifiedCredentialEntry,
  search: string,
  teamNameById: Map<string, string>
): boolean {
  const q = search.trim().toLowerCase()
  if (!q) return true

  if (entry.kind === 'full') {
    const c = entry.credential
    const affiliation = affiliationLabel(entry, teamNameById)
    const contributor = credentialProviderLabel(c)
    return (
      c.name.toLowerCase().includes(q) ||
      c.provider.toLowerCase().includes(q) ||
      providerLabel(c.provider).toLowerCase().includes(q) ||
      affiliation.toLowerCase().includes(q) ||
      contributor.toLowerCase().includes(q) ||
      c.api_key_masked.toLowerCase().includes(q)
    )
  }

  const s = entry.summary
  const contributor = credentialProviderLabel(s)
  return (
    s.name.toLowerCase().includes(q) ||
    s.provider.toLowerCase().includes(q) ||
    providerLabel(s.provider).toLowerCase().includes(q) ||
    contributor.toLowerCase().includes(q) ||
    '系统'.includes(q)
  )
}

function scopeSortRank(scope: ProviderCredential['scope'] | CredentialSummary['scope']): number {
  if (scope === 'user') return 0
  if (scope === 'team') return 1
  if (scope === 'system') return 2
  return 3
}

export function sortUnifiedCredentialEntries(
  entries: readonly UnifiedCredentialEntry[],
  teamNameById: Map<string, string>
): UnifiedCredentialEntry[] {
  return [...entries].sort((a, b) => {
    const scopeA = entryScope(a)
    const scopeB = entryScope(b)
    const scopeDiff = scopeSortRank(scopeA) - scopeSortRank(scopeB)
    if (scopeDiff !== 0) return scopeDiff

    if (scopeA === 'team') {
      const teamDiff = affiliationLabel(a, teamNameById).localeCompare(
        affiliationLabel(b, teamNameById),
        'zh-CN'
      )
      if (teamDiff !== 0) return teamDiff
    }

    const nameA = a.kind === 'full' ? a.credential.name : a.summary.name
    const nameB = b.kind === 'full' ? b.credential.name : b.summary.name
    return nameA.localeCompare(nameB, 'zh-CN')
  })
}

export function countUnifiedCredentialsByScope(
  entries: readonly UnifiedCredentialEntry[]
): UnifiedCredentialsScopeCounts {
  let personal = 0
  let team = 0
  let system = 0
  for (const entry of entries) {
    const scope = entryScope(entry)
    if (scope === 'user') personal += 1
    else if (scope === 'team') team += 1
    else if (scope === 'system') system += 1
  }
  return { personal, team, system, total: entries.length }
}

export function filterUnifiedCredentialEntries(
  entries: readonly UnifiedCredentialEntry[],
  options: Readonly<{
    search: string
    scopeFilter: UnifiedCredentialScopeFilter
    teamNameById: Map<string, string>
  }>
): UnifiedCredentialEntry[] {
  const filtered = entries.filter(
    (entry) =>
      matchesScopeFilter(entry, options.scopeFilter) &&
      matchesCredentialSearch(entry, options.search, options.teamNameById)
  )
  return sortUnifiedCredentialEntries(filtered, options.teamNameById)
}

export function paginateUnifiedCredentialEntries(
  entries: readonly UnifiedCredentialEntry[],
  page: number,
  pageSize: number = DEFAULT_PAGE_SIZE
): UnifiedCredentialsPaginationSlice {
  const total = entries.length
  const safePageSize = Math.max(1, pageSize)
  const pages = total <= 0 ? 1 : Math.max(1, Math.ceil(total / safePageSize))
  const safePage = Math.min(Math.max(1, page), pages)
  const start = (safePage - 1) * safePageSize
  const items = entries.slice(start, start + safePageSize)

  return {
    items,
    page: safePage,
    page_size: safePageSize,
    total,
    has_next: safePage < pages,
    has_prev: safePage > 1,
  }
}
