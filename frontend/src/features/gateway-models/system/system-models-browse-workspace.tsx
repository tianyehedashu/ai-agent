import { useDeferredValue, useMemo, useState } from 'react'

import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import type { HealthFilter } from '@/features/gateway-models/constants'
import { useInfiniteGatewayModelPages } from '@/features/gateway-models/hooks/use-infinite-gateway-model-pages'
import {
  fromGatewayModel,
  GatewayModelFlatList,
  GatewayModelListShell,
  GatewayModelListToolbar,
  SYSTEM_BROWSE_CAPABILITIES,
} from '@/features/gateway-models/list'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { Loader2 } from '@/lib/lucide-icons'
import { MODEL_PROVIDERS } from '@/types/user-model'

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

  const {
    items: requestableItems,
    isLoading,
    isFetching,
    refetch,
  } = useInfiniteGatewayModelPages(
    teamId,
    { registry_scope: 'requestable' },
    { prefetchMode: 'idle' }
  )

  const systemModels = useMemo(
    () => requestableItems.filter((m) => m.registry_kind === 'system'),
    [requestableItems]
  )

  const providerChoices = useMemo(() => {
    const s = new Set<string>(MODEL_PROVIDERS.map((p) => p.id))
    for (const m of systemModels) {
      s.add(m.provider)
    }
    return Array.from(s).sort()
  }, [systemModels])

  const filteredItems = useMemo(() => {
    const q = deferredSearch.trim().toLowerCase()
    return systemModels.filter((m) => {
      if (providerFilter && m.provider !== providerFilter) return false
      if (
        abilityFilter &&
        m.capability !== abilityFilter &&
        !m.model_types?.includes(abilityFilter)
      ) {
        return false
      }
      if (!q) return true
      const haystack = [m.name, m.real_model, m.provider, m.credential_name ?? '']
        .join(' ')
        .toLowerCase()
      return haystack.includes(q)
    })
  }, [systemModels, deferredSearch, providerFilter, abilityFilter])

  const listItems = useMemo(
    () => filteredItems.map((m) => fromGatewayModel(m, 'system')),
    [filteredItems]
  )

  const capabilities = SYSTEM_BROWSE_CAPABILITIES
  const healthFilter: HealthFilter = 'all'

  if (isLoading) {
    return <BrowseFallback />
  }

  if (systemModels.length === 0) {
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
              只读 · {systemModels.length} 个可请求
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
          onHealthFilterChange={() => {}}
          allModels={systemModels}
          usageDays={7}
          onUsageDaysChange={() => {}}
          canWrite={false}
        />
      }
      isEmpty={listItems.length === 0}
      emptySlot={<p className="px-3 py-12 text-center text-sm text-muted-foreground">无匹配模型</p>}
    >
      <GatewayModelFlatList capabilities={capabilities} items={listItems} />
    </GatewayModelListShell>
  )
}
