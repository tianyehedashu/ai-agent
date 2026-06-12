/**
 * 调用日志页筛选下拉的数据源 Hook。
 *
 * 凭据筛选项与统一凭据 / 配额中心一致，使用 actor 维度聚合（非 URL `:teamId`）。
 * 人员筛选已改用 useTeamMemberFilterSearch（服务端搜索），本 hook 不再提供 memberOptions。
 */

import { useMemo } from 'react'

import { useActorCredentialSummaries } from '@/features/gateway-credentials/hooks/use-actor-credential-summaries'
import { useGatewayVirtualKeys } from '@/features/gateway-keys/use-gateway-virtual-keys'
import { useInfiniteGatewayModelPages } from '@/features/gateway-models/hooks/use-infinite-gateway-model-pages'
import type { GatewayFilterOption } from '@/features/gateway-usage/gateway-filter-combobox'
import {
  credentialFilterOptions,
  keyFilterOptions,
  modelFilterOptionsForStats,
} from '@/features/gateway-usage/usage-stats-filter-catalog'

export interface UseLogFilterCatalogParams {
  teamId: string
}

export interface LogFilterCatalogResult {
  credentialOptions: GatewayFilterOption[]
  keyOptions: GatewayFilterOption[]
  modelOptions: GatewayFilterOption[]
  credentialsLoading: boolean
  keysLoading: boolean
  modelsLoading: boolean
}

export function useLogFilterCatalog({ teamId }: UseLogFilterCatalogParams): LogFilterCatalogResult {
  const actorCredentials = useActorCredentialSummaries()

  const teamKeysQuery = useGatewayVirtualKeys(teamId)

  const teamModels = useInfiniteGatewayModelPages(
    teamId,
    { registry_scope: 'callable' },
    { prefetchMode: 'open' }
  )

  const credentialOptions = useMemo(
    () => credentialFilterOptions(actorCredentials.list),
    [actorCredentials.list]
  )

  const keyOptions = useMemo(() => keyFilterOptions(teamKeysQuery.data ?? []), [teamKeysQuery.data])

  const modelOptions = useMemo(
    () => modelFilterOptionsForStats(teamModels.items),
    [teamModels.items]
  )

  return {
    credentialOptions,
    keyOptions,
    modelOptions,
    credentialsLoading: actorCredentials.isLoading,
    keysLoading: teamKeysQuery.isLoading,
    modelsLoading: teamModels.isLoading,
  }
}
