/**
 * 统一凭据列表：聚合个人 + 团队 + 系统，客户端筛选与分页。
 */

import { useDeferredValue, useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import type { ProviderCredential } from '@/api/gateway'
import { credentialsApi, fetchAllManagedTeamCredentials } from '@/api/gateway/credentials'
import { MY_CREDENTIALS_QUERY_KEY } from '@/features/gateway-credentials/query-keys'
import {
  countUnifiedCredentialsByScope,
  filterUnifiedCredentialEntries,
  paginateUnifiedCredentialEntries,
  type UnifiedCredentialEntry,
  type UnifiedCredentialScopeFilter,
  type UnifiedCredentialsScopeCounts,
} from '@/features/gateway-credentials/unified/unified-credentials-filters'
import { useGatewayTeamNameMap } from '@/features/gateway-teams/use-gateway-teams'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { DEFAULT_PAGE_SIZE } from '@/lib/pagination'
import { useCurrentUser } from '@/stores/user'

export type {
  UnifiedCredentialEntry,
  UnifiedCredentialScopeFilter,
} from '@/features/gateway-credentials/unified/unified-credentials-filters'

export interface UseUnifiedCredentialsListOptions {
  search: string
  scopeFilter: UnifiedCredentialScopeFilter
  page: number
  pageSize?: number
}

export interface UnifiedCredentialsListResult {
  items: readonly UnifiedCredentialEntry[]
  isLoading: boolean
  isFetching: boolean
  refetch: () => Promise<unknown>
  /** 全量（未筛选）各归属计数 */
  counts: UnifiedCredentialsScopeCounts
  /** 当前筛选命中总数 */
  filteredTotal: number
  /** 全量个人凭据（供验证 / 导入，不受分页影响） */
  personalCredentials: readonly ProviderCredential[]
  /** management_access=full 的团队凭据（供复制源判断） */
  copyableTeamCredentials: readonly ProviderCredential[]
  pagination: {
    page: number
    page_size: number
    total: number
    has_next: boolean
    has_prev: boolean
  }
}

function mergeRawEntries(
  personal: readonly ProviderCredential[],
  team: readonly ProviderCredential[],
  system: readonly UnifiedCredentialEntry[]
): UnifiedCredentialEntry[] {
  const seen = new Set<string>()
  const entries: UnifiedCredentialEntry[] = []

  for (const credential of personal) {
    if (seen.has(credential.id)) continue
    seen.add(credential.id)
    entries.push({ kind: 'full', credential })
  }

  for (const credential of team) {
    if (seen.has(credential.id)) continue
    seen.add(credential.id)
    entries.push({ kind: 'full', credential })
  }

  for (const entry of system) {
    const id = entry.kind === 'full' ? entry.credential.id : entry.summary.id
    if (seen.has(id)) continue
    seen.add(id)
    entries.push(entry)
  }

  return entries
}

export function useUnifiedCredentialsList({
  search,
  scopeFilter,
  page,
  pageSize = DEFAULT_PAGE_SIZE,
}: UseUnifiedCredentialsListOptions): UnifiedCredentialsListResult {
  const teamId = useGatewayTeamId()
  const currentUser = useCurrentUser()
  const hasAuthSession = currentUser !== null
  const { isPlatformAdmin } = useGatewayPermission()
  const teamNameById = useGatewayTeamNameMap()
  const deferredSearch = useDeferredValue(search)

  const personalQuery = useQuery({
    queryKey: MY_CREDENTIALS_QUERY_KEY,
    queryFn: () => credentialsApi.listMyCredentials(),
    enabled: hasAuthSession,
  })

  const teamQuery = useQuery({
    queryKey: ['gateway', 'unified-credentials', 'managed-team'],
    queryFn: () => fetchAllManagedTeamCredentials(),
    enabled: hasAuthSession,
  })

  const systemQuery = useQuery({
    queryKey: ['gateway', 'unified-credentials', 'system', teamId, isPlatformAdmin],
    queryFn: async (): Promise<UnifiedCredentialEntry[]> => {
      if (!teamId) return []
      if (isPlatformAdmin) {
        const rows = await credentialsApi.listCredentials(teamId)
        return rows
          .filter((c) => c.scope === 'system')
          .map((credential) => ({ kind: 'full' as const, credential }))
      }
      const summaries = await credentialsApi.listCredentialSummaries(teamId)
      return summaries
        .filter((s) => s.scope === 'system')
        .map((summary) => ({ kind: 'summary' as const, summary }))
    },
    enabled: hasAuthSession && Boolean(teamId),
  })

  const rawEntries = useMemo(
    () => mergeRawEntries(personalQuery.data ?? [], teamQuery.data ?? [], systemQuery.data ?? []),
    [personalQuery.data, systemQuery.data, teamQuery.data]
  )

  const counts = useMemo(() => countUnifiedCredentialsByScope(rawEntries), [rawEntries])

  const personalCredentials = useMemo(
    () =>
      rawEntries
        .filter((entry) => entry.kind === 'full' && entry.credential.scope === 'user')
        .map((entry) => (entry.kind === 'full' ? entry.credential : null))
        .filter((c): c is ProviderCredential => c !== null),
    [rawEntries]
  )

  const copyableTeamCredentials = useMemo(
    () => (teamQuery.data ?? []).filter((c) => c.management_access !== 'metadata'),
    [teamQuery.data]
  )

  const filteredEntries = useMemo(
    () =>
      filterUnifiedCredentialEntries(rawEntries, {
        search: deferredSearch,
        scopeFilter,
        teamNameById,
      }),
    [deferredSearch, rawEntries, scopeFilter, teamNameById]
  )

  const paginationSlice = useMemo(
    () => paginateUnifiedCredentialEntries(filteredEntries, page, pageSize),
    [filteredEntries, page, pageSize]
  )

  const refetch = (): Promise<unknown> =>
    Promise.all([personalQuery.refetch(), teamQuery.refetch(), systemQuery.refetch()])

  const isLoading = personalQuery.isLoading || teamQuery.isLoading || systemQuery.isLoading
  const isFetching = personalQuery.isFetching || teamQuery.isFetching || systemQuery.isFetching

  return {
    items: paginationSlice.items,
    isLoading,
    isFetching,
    refetch,
    counts,
    filteredTotal: filteredEntries.length,
    personalCredentials,
    copyableTeamCredentials,
    pagination: {
      page: paginationSlice.page,
      page_size: paginationSlice.page_size,
      total: paginationSlice.total,
      has_next: paginationSlice.has_next,
      has_prev: paginationSlice.has_prev,
    },
  }
}

export function listVariantForCredential(
  credential: ProviderCredential
): 'personal' | 'team' | 'system' {
  if (credential.scope === 'user') return 'personal'
  if (credential.scope === 'system') return 'system'
  return 'team'
}

export function listTabForCredential(
  credential: ProviderCredential
): 'personal' | 'shared' | 'system' {
  if (credential.scope === 'user') return 'personal'
  if (credential.scope === 'system') return 'system'
  return 'shared'
}
