/**
 * 统一模型列表：聚合个人 + 团队 + 系统，客户端筛选与分页。
 */

import { useDeferredValue, useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import { credentialsApi } from '@/api/gateway/credentials'
import { fetchAllGatewayModelPages, fetchAllManagedTeamModelPages } from '@/api/gateway/models'
import { fetchAllPersonalGatewayModels } from '@/api/gateway/my-models'
import { MY_CREDENTIALS_QUERY_KEY } from '@/features/gateway-credentials/query-keys'
import type { HealthFilter } from '@/features/gateway-models/constants'
import { fromGatewayModel, fromPersonalModel } from '@/features/gateway-models/list/adapters'
import type { GatewayModelListItem } from '@/features/gateway-models/list/types'
import { UNIFIED_MODELS_QUERY_KEY } from '@/features/gateway-models/unified/invalidate-unified-models-cache'
import {
  countUnifiedModelsByScope,
  filterUnifiedModelEntries,
  matchesHealthFilter,
  paginateUnifiedModelEntries,
  summarizeUnifiedModelsHealth,
  type UnifiedModelScopeFilter,
  type UnifiedModelsScopeCounts,
} from '@/features/gateway-models/unified/unified-models-filters'
import { useGatewayTeamNameMap } from '@/features/gateway-teams/use-gateway-teams'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useCurrentUser } from '@/stores/user'
import { MODEL_PROVIDERS } from '@/types/user-model'

/** 统一模型列表客户端分页每页条数 */
const UNIFIED_MODELS_PAGE_SIZE = 15

export type { UnifiedModelScopeFilter } from '@/features/gateway-models/unified/unified-models-filters'

export interface UseUnifiedModelsListOptions {
  search: string
  scopeFilter: UnifiedModelScopeFilter
  page: number
  pageSize?: number
  providerFilter?: string
  healthFilter?: HealthFilter
  credentialFilter?: string
  teamFilter?: string
}

export interface UnifiedModelsListResult {
  items: readonly GatewayModelListItem[]
  /** 当前筛选下全量（未分页，含健康筛选） */
  filteredEntries: readonly GatewayModelListItem[]
  /** 除健康筛选外的当前结果（探活统计 / 批量运维基准） */
  entriesBeforeHealthFilter: readonly GatewayModelListItem[]
  isLoading: boolean
  isFetching: boolean
  refetch: () => Promise<unknown>
  counts: UnifiedModelsScopeCounts
  filteredTotal: number
  connectivitySummary: {
    total: number
    success: number
    failed: number
    unknown: number
  }
  providerChoices: readonly string[]
  /** 列表中出现过的团队 ID（用于团队筛选下拉） */
  teamIdsWithModels: readonly string[]
  pagination: {
    page: number
    page_size: number
    total: number
    has_next: boolean
    has_prev: boolean
  }
}

function mergeRawItems(
  personal: readonly GatewayModelListItem[],
  team: readonly GatewayModelListItem[],
  system: readonly GatewayModelListItem[]
): GatewayModelListItem[] {
  const seen = new Set<string>()
  const items: GatewayModelListItem[] = []

  for (const item of [...personal, ...team, ...system]) {
    const key = `${item.scope}:${item.id}`
    if (seen.has(key)) continue
    seen.add(key)
    items.push(item)
  }

  return items
}

function enrichCredentialNames(
  items: readonly GatewayModelListItem[],
  credentialNameById: ReadonlyMap<string, string>
): GatewayModelListItem[] {
  if (credentialNameById.size === 0) return [...items]
  return items.map((item) => {
    if (item.credentialName?.trim()) return item
    const credId = item.credentialId
    if (!credId) return item
    const name = credentialNameById.get(credId)?.trim()
    if (!name) return item
    return { ...item, credentialName: name }
  })
}

export function useUnifiedModelsList({
  search,
  scopeFilter,
  page,
  pageSize = UNIFIED_MODELS_PAGE_SIZE,
  providerFilter = '',
  healthFilter = 'all',
  credentialFilter = '',
  teamFilter = '',
}: UseUnifiedModelsListOptions): UnifiedModelsListResult {
  const teamId = useGatewayTeamId()
  const currentUser = useCurrentUser()
  const hasAuthSession = currentUser !== null
  const { isPlatformAdmin } = useGatewayPermission()
  const teamNameById = useGatewayTeamNameMap()
  const deferredSearch = useDeferredValue(search)

  const personalQuery = useQuery({
    queryKey: [...UNIFIED_MODELS_QUERY_KEY, 'personal'],
    queryFn: async () => {
      const rows = await fetchAllPersonalGatewayModels()
      return rows.map(fromPersonalModel)
    },
    enabled: hasAuthSession,
  })

  const personalCredentialsQuery = useQuery({
    queryKey: MY_CREDENTIALS_QUERY_KEY,
    queryFn: () => credentialsApi.listMyCredentials(),
    enabled: hasAuthSession,
  })

  const credentialNameById = useMemo(() => {
    const map = new Map<string, string>()
    for (const credential of personalCredentialsQuery.data ?? []) {
      const name = credential.name.trim()
      if (name) map.set(credential.id, name)
    }
    return map
  }, [personalCredentialsQuery.data])

  const teamQuery = useQuery({
    queryKey: [...UNIFIED_MODELS_QUERY_KEY, 'managed-team'],
    queryFn: async () => {
      const rows = await fetchAllManagedTeamModelPages()
      return rows.map((m) => fromGatewayModel(m, 'team'))
    },
    enabled: hasAuthSession,
  })

  const systemQuery = useQuery({
    queryKey: [...UNIFIED_MODELS_QUERY_KEY, 'system', teamId, isPlatformAdmin],
    queryFn: async () => {
      if (!teamId) return []
      const registryScope = isPlatformAdmin ? 'system' : 'system_requestable'
      const rows = await fetchAllGatewayModelPages(teamId, { registry_scope: registryScope })
      return rows.map((m) => fromGatewayModel(m, 'system'))
    },
    enabled: hasAuthSession && teamId.length > 0,
  })

  const rawItems = useMemo(
    () =>
      enrichCredentialNames(
        mergeRawItems(personalQuery.data ?? [], teamQuery.data ?? [], systemQuery.data ?? []),
        credentialNameById
      ),
    [personalQuery.data, teamQuery.data, systemQuery.data, credentialNameById]
  )

  const counts = useMemo(() => countUnifiedModelsByScope(rawItems), [rawItems])

  const teamIdsWithModels = useMemo(() => {
    const ids = new Set<string>()
    for (const item of rawItems) {
      if (item.teamId) ids.add(item.teamId)
    }
    return [...ids].sort((a, b) =>
      (teamNameById.get(a) ?? a).localeCompare(teamNameById.get(b) ?? b, 'zh-CN')
    )
  }, [rawItems, teamNameById])

  const baseFilteredEntries = useMemo(
    () =>
      filterUnifiedModelEntries(rawItems, {
        search: deferredSearch,
        scopeFilter,
        teamNameById,
        providerFilter,
        healthFilter: 'all',
        credentialFilter,
        teamFilter,
      }),
    [
      rawItems,
      deferredSearch,
      scopeFilter,
      teamNameById,
      providerFilter,
      credentialFilter,
      teamFilter,
    ]
  )

  const filteredEntries = useMemo(
    () =>
      healthFilter === 'all'
        ? baseFilteredEntries
        : baseFilteredEntries.filter((item) => matchesHealthFilter(item, healthFilter)),
    [baseFilteredEntries, healthFilter]
  )

  /** 探活统计基于除健康筛选外的当前结果，避免筛到空集后无法切回 */
  const connectivitySummary = useMemo(
    () => summarizeUnifiedModelsHealth(baseFilteredEntries),
    [baseFilteredEntries]
  )

  const providerChoices = useMemo(() => {
    const s = new Set<string>(MODEL_PROVIDERS.map((p) => p.id))
    for (const item of rawItems) {
      s.add(item.provider)
    }
    return Array.from(s).sort()
  }, [rawItems])

  const paginationSlice = useMemo(
    () => paginateUnifiedModelEntries(filteredEntries, page, pageSize),
    [filteredEntries, page, pageSize]
  )

  const refetch = (): Promise<unknown> =>
    Promise.all([personalQuery.refetch(), teamQuery.refetch(), systemQuery.refetch()])

  return {
    items: paginationSlice.items,
    filteredEntries,
    entriesBeforeHealthFilter: baseFilteredEntries,
    isLoading:
      personalQuery.isLoading ||
      personalCredentialsQuery.isLoading ||
      teamQuery.isLoading ||
      systemQuery.isLoading,
    isFetching:
      personalQuery.isFetching ||
      personalCredentialsQuery.isFetching ||
      teamQuery.isFetching ||
      systemQuery.isFetching,
    refetch,
    counts,
    filteredTotal: filteredEntries.length,
    connectivitySummary,
    providerChoices,
    teamIdsWithModels,
    pagination: {
      page: paginationSlice.page,
      page_size: paginationSlice.page_size,
      total: paginationSlice.total,
      has_next: paginationSlice.has_next,
      has_prev: paginationSlice.has_prev,
    },
  }
}
