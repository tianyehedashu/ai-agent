import { useDeferredValue, useEffect, useMemo, useState } from 'react'

import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { gatewayApi, type GatewayModel } from '@/api/gateway'
import { PaginationControls } from '@/components/pagination-controls'
import { Badge } from '@/components/ui/badge'
import type { HealthFilter } from '@/features/gateway-models/constants'
import {
  fromGatewayModel,
  GatewayModelFlatList,
  GatewayModelListShell,
  GatewayModelListToolbar,
  SYSTEM_BROWSE_CAPABILITIES,
} from '@/features/gateway-models/list'
import { gatewayModelsListQueryKey } from '@/features/gateway-models/utils'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { Loader2 } from '@/lib/lucide-icons'
import { buildFilterKey, DEFAULT_PAGE_SIZE, usePaginationPageForFilters } from '@/lib/pagination'
import { MODEL_PROVIDERS } from '@/types/user-model'

const SYSTEM_BROWSE_PAGE_SIZE = DEFAULT_PAGE_SIZE
const EMPTY_SYSTEM_ITEMS: GatewayModel[] = []

function BrowseFallback(): React.JSX.Element {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />
      加载系统模型…
    </div>
  )
}

export function SystemModelsBrowseWorkspace(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)
  const [providerFilter, setProviderFilter] = useState('')
  const [abilityFilter, setAbilityFilter] = useState('')
  const [healthFilter, setHealthFilter] = useState<HealthFilter>('all')

  const filterKey = buildFilterKey([deferredSearch, providerFilter, abilityFilter, healthFilter])
  const [page, setPage] = usePaginationPageForFilters(filterKey)

  const {
    data: listData,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: gatewayModelsListQueryKey(
      teamId,
      'system_requestable',
      providerFilter,
      '',
      page,
      SYSTEM_BROWSE_PAGE_SIZE,
      deferredSearch,
      healthFilter,
      abilityFilter
    ),
    queryFn: () =>
      gatewayApi.listModels(teamId, {
        registry_scope: 'system_requestable',
        page,
        page_size: SYSTEM_BROWSE_PAGE_SIZE,
        ...(providerFilter ? { provider: providerFilter } : {}),
        ...(abilityFilter ? { type: abilityFilter } : {}),
        ...(deferredSearch.trim() ? { q: deferredSearch.trim() } : {}),
        ...(healthFilter !== 'all' ? { connectivity: healthFilter } : {}),
      }),
    placeholderData: keepPreviousData,
  })

  const registryItems = listData?.items ?? EMPTY_SYSTEM_ITEMS
  const total = listData?.total ?? 0

  useEffect(() => {
    if (!listData) return
    const maxPage = Math.max(1, Math.ceil(listData.total / listData.page_size))
    if (page > maxPage) {
      setPage(maxPage)
    }
  }, [listData, page, setPage])

  const providerChoices = useMemo(() => {
    const s = new Set<string>(MODEL_PROVIDERS.map((p) => p.id))
    if (providerFilter === '' && registryItems.length > 0) {
      for (const m of registryItems) {
        s.add(m.provider)
      }
    }
    return Array.from(s).sort()
  }, [registryItems, providerFilter])

  const listItems = useMemo(
    () => registryItems.map((m) => fromGatewayModel(m, 'system')),
    [registryItems]
  )

  const capabilities = SYSTEM_BROWSE_CAPABILITIES

  if (isLoading) {
    return <BrowseFallback />
  }

  if (total === 0 && filterKey === buildFilterKey(['', '', '', 'all'])) {
    return (
      <div className="rounded-lg border border-dashed bg-muted/10 p-8 text-center text-sm text-muted-foreground">
        当前工作区暂无可请求的系统模型。请联系平台管理员配置系统供给，或查看{' '}
        <Link to="/gateway/guide" className="text-primary underline-offset-4 hover:underline">
          调用指南
        </Link>
        。
      </div>
    )
  }

  return (
    <GatewayModelListShell
      capabilities={capabilities}
      headerSlot={
        <div className="space-y-1 border-b px-3 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold">系统模型</h3>
            <Badge variant="secondary" className="text-xs font-normal">
              只读 · {total} 个可请求
            </Badge>
            <div className="ml-auto">
              <GatewayRefreshButton
                isFetching={isFetching}
                ariaLabel="刷新系统模型"
                onRefresh={() => refetch()}
              />
            </div>
          </div>
          <p className="text-sm text-muted-foreground">
            以下模型由系统预置，可直接通过{' '}
            <Link to="/gateway/keys" className="text-primary underline-offset-4 hover:underline">
              虚拟 Key
            </Link>{' '}
            或{' '}
            <Link to="/gateway/guide" className="text-primary underline-offset-4 hover:underline">
              调用指南
            </Link>{' '}
            使用。如需管理团队自注册别名，请切换到「团队」Tab 并注册模型。
          </p>
        </div>
      }
      toolbar={
        <GatewayModelListToolbar
          capabilities={capabilities}
          search={search}
          onSearchChange={setSearch}
          providerFilter={providerFilter}
          onProviderFilterChange={setProviderFilter}
          abilityFilter={abilityFilter}
          onAbilityFilterChange={setAbilityFilter}
          providerChoices={providerChoices}
          healthFilter={healthFilter}
          onHealthFilterChange={setHealthFilter}
          connectivitySummary={listData?.connectivity_summary}
          allModels={registryItems}
          usageDays={7}
          onUsageDaysChange={() => {}}
          canWrite={false}
        />
      }
      isEmpty={registryItems.length === 0}
      emptySlot={<p className="px-3 py-12 text-center text-sm text-muted-foreground">无匹配模型</p>}
      paginationSlot={
        total > 0 && listData ? (
          <div className="border-t px-3 py-2">
            <PaginationControls
              page={listData.page}
              page_size={listData.page_size}
              total={listData.total}
              has_next={listData.has_next}
              has_prev={listData.has_prev}
              onPageChange={setPage}
            />
          </div>
        ) : undefined
      }
    >
      <GatewayModelFlatList capabilities={capabilities} items={listItems} />
    </GatewayModelListShell>
  )
}
