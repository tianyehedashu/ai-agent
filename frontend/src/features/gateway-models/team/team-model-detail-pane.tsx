import { useCallback, useMemo, useState } from 'react'

import { useQuery } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { gatewayApi, type GatewayModelUpdateBody } from '@/api/gateway'
import type { UsagePeriodDays } from '@/features/gateway-models/constants'
import { parseScopeTab } from '@/features/gateway-models/constants'
import { canDeleteGatewayModel } from '@/features/gateway-models/gateway-model-permissions'
import { useGatewayModelMutations } from '@/features/gateway-models/hooks/use-gateway-model-mutations'
import {
  systemModelsFilteredHref,
  teamModelsFilteredHref,
  teamModelsIndexHref,
} from '@/features/gateway-models/paths'
import {
  gatewayModelsListQueryKey,
  resolveTeamModelsRegistryScope,
} from '@/features/gateway-models/utils'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { Loader2 } from '@/lib/lucide-icons'

import { ModelInspector } from './model-inspector'

interface TeamModelDetailPaneProps {
  modelId: string
}

export function TeamModelDetailPane({ modelId }: TeamModelDetailPaneProps): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const navigate = useNavigate()
  const { canWrite, isPlatformAdmin } = useGatewayPermission()
  const [searchParams] = useSearchParams()
  const credentialFilter = searchParams.get('credentialId') ?? ''
  const scopeTab = parseScopeTab(searchParams.get('tab'), { allowSystem: isPlatformAdmin })
  const listMode = scopeTab === 'system' ? 'system' : 'team'
  const registryScope = resolveTeamModelsRegistryScope(listMode, credentialFilter)
  const [usageDays] = useState<UsagePeriodDays>(7)

  const { data: items, isLoading } = useQuery({
    queryKey: gatewayModelsListQueryKey(teamId, registryScope, '', credentialFilter),
    queryFn: () =>
      gatewayApi.listModels(teamId, {
        registry_scope: registryScope,
        ...(credentialFilter ? { credential_id: credentialFilter } : {}),
      }),
  })

  const trySystemFallback =
    !isLoading && isPlatformAdmin && registryScope !== 'system' && modelId !== ''

  const { data: systemFallbackItems, isLoading: systemFallbackLoading } = useQuery({
    queryKey: gatewayModelsListQueryKey(teamId, 'system', '', ''),
    queryFn: () => gatewayApi.listModels(teamId, { registry_scope: 'system' }),
    enabled: trySystemFallback,
  })

  const listHref =
    credentialFilter !== ''
      ? scopeTab === 'system'
        ? systemModelsFilteredHref(teamId, credentialFilter)
        : teamModelsFilteredHref(teamId, credentialFilter)
      : scopeTab === 'system'
        ? systemModelsFilteredHref(teamId)
        : teamModelsIndexHref(teamId)

  const { data: usageSummary, isLoading: usageLoading } = useQuery({
    queryKey: ['gateway', 'models', 'usage-summary', teamId, '', usageDays],
    queryFn: () => gatewayApi.modelsUsageSummary(teamId, { days: usageDays }),
  })

  const { data: routes } = useQuery({
    queryKey: ['gateway', 'routes', teamId],
    queryFn: () => gatewayApi.listRoutes(teamId),
    enabled: modelId !== '',
  })

  const { data: credentials } = useQuery({
    queryKey: ['gateway', 'credentials', teamId],
    queryFn: () => gatewayApi.listCredentials(teamId),
    enabled: canWrite || isPlatformAdmin,
  })

  const usageByRouteName = useMemo(() => {
    const m = new Map<string, NonNullable<typeof usageSummary>['items'][number]>()
    for (const row of usageSummary?.items ?? []) {
      m.set(row.route_name, row)
    }
    return m
  }, [usageSummary])

  const model = useMemo(() => {
    const fromPrimary = (items ?? []).find((m) => m.id === modelId)
    if (fromPrimary) return fromPrimary
    return (systemFallbackItems ?? []).find((m) => m.id === modelId) ?? null
  }, [items, systemFallbackItems, modelId])

  const { updateModelMutation, testMutation, deleteModelMutation } = useGatewayModelMutations({
    credentialId: credentialFilter || undefined,
    onDeleteSuccess: () => {
      navigate(listHref)
    },
  })

  const handleTest = useCallback(
    (id: string): void => {
      testMutation.mutate(id)
    },
    [testMutation]
  )

  const handleSave = useCallback(
    (id: string, body: GatewayModelUpdateBody): void => {
      updateModelMutation.mutate({ id, body })
    },
    [updateModelMutation]
  )

  const handleToggleEnabled = useCallback(
    (id: string, enabled: boolean): void => {
      updateModelMutation.mutate({ id, body: { enabled } })
    },
    [updateModelMutation]
  )

  const handleDelete = useCallback(
    (id: string): void => {
      if (!model) return
      if (
        !window.confirm(
          `确定删除模型「${model.name}」？将同步更新虚拟 Key / 路由中的模型白名单，此操作不可撤销。`
        )
      ) {
        return
      }
      deleteModelMutation.mutate(id)
    },
    [model, deleteModelMutation]
  )

  const canDelete = model ? canDeleteGatewayModel(model, canWrite, isPlatformAdmin) : false

  if (isLoading || (trySystemFallback && systemFallbackLoading && !model)) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        加载模型…
      </div>
    )
  }

  if (!model) {
    return (
      <p className="py-12 text-center text-sm text-muted-foreground">
        未找到该模型，可能已被删除或你无权访问。
      </p>
    )
  }

  return (
    <ModelInspector
      model={model}
      credentials={credentials ?? []}
      routes={routes ?? []}
      usageDays={usageDays}
      usageRow={usageByRouteName.get(model.name)}
      usageLoading={usageLoading}
      isTesting={testMutation.isPending && testMutation.variables === model.id}
      isSaving={updateModelMutation.isPending}
      isDeleting={deleteModelMutation.isPending}
      canDelete={canDelete}
      onTest={handleTest}
      onSave={handleSave}
      onToggleEnabled={handleToggleEnabled}
      onDelete={handleDelete}
    />
  )
}
