import { useCallback, useMemo, useState } from 'react'

import { useQuery } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { gatewayApi, type GatewayModelUpdateBody } from '@/api/gateway'
import type { UsagePeriodDays } from '@/features/gateway-models/constants'
import { parseModelsScopeTab } from '@/features/gateway-models/constants'
import { GatewayModelDeleteConfirmDialog } from '@/features/gateway-models/detail/gateway-model-delete-confirm-dialog'
import {
  ModelDetailLoadingState,
  ModelDetailNotFoundState,
} from '@/features/gateway-models/detail/model-detail-states'
import { ModelInspector } from '@/features/gateway-models/detail/model-inspector'
import { useGatewayModelMutations } from '@/features/gateway-models/hooks/use-gateway-model-mutations'
import { resolveUnifiedModelsReturnHref } from '@/features/gateway-models/paths'
import { indexUsageByRouteName } from '@/features/gateway-models/usage-summary-index'
import { resolveTeamModelsRegistryScope } from '@/features/gateway-models/utils'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'

interface TeamModelDetailPaneProps {
  modelId: string
}

export function TeamModelDetailPane({ modelId }: TeamModelDetailPaneProps): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const navigate = useNavigate()
  const { canWrite, isPlatformAdmin } = useGatewayPermission()
  const [searchParams] = useSearchParams()
  const credentialFilter = searchParams.get('credentialId') ?? ''
  const scopeTab = parseModelsScopeTab(searchParams.get('tab'))
  const listMode = scopeTab === 'system' ? 'system' : 'team'
  const registryScope = resolveTeamModelsRegistryScope(listMode, credentialFilter)
  const [usageDays] = useState<UsagePeriodDays>(7)
  const [deleteOpen, setDeleteOpen] = useState(false)

  const { data: primaryModel, isLoading } = useQuery({
    queryKey: ['gateway', 'models', teamId, modelId, registryScope],
    queryFn: () =>
      gatewayApi.getModel(teamId, modelId, {
        registry_scope: registryScope,
      }),
    enabled: modelId !== '',
    retry: false,
  })

  const trySystemFallback =
    !isLoading && !primaryModel && isPlatformAdmin && registryScope !== 'system' && modelId !== ''

  const { data: systemFallbackModel, isLoading: systemFallbackLoading } = useQuery({
    queryKey: ['gateway', 'models', teamId, modelId, 'system'],
    queryFn: () => gatewayApi.getModel(teamId, modelId, { registry_scope: 'system' }),
    enabled: trySystemFallback,
  })

  const model = primaryModel ?? systemFallbackModel ?? null
  const resolvedRouteName = model?.name ?? ''

  const listHref = resolveUnifiedModelsReturnHref(teamId, searchParams, {
    scope: scopeTab === 'system' ? 'system' : undefined,
    credentialId: credentialFilter || undefined,
  })

  const { data: usageSummary, isLoading: usageLoading } = useQuery({
    queryKey: ['gateway', 'models', 'usage-summary', teamId, resolvedRouteName, usageDays],
    queryFn: () =>
      gatewayApi.modelsUsageSummary(teamId, {
        days: usageDays,
        route_names: [resolvedRouteName],
      }),
    enabled: resolvedRouteName !== '',
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

  const usageByRouteName = useMemo(
    () => indexUsageByRouteName(usageSummary?.items),
    [usageSummary?.items]
  )

  const { updateModelMutation, testMutation, deleteModelMutation } = useGatewayModelMutations({
    credentialId: credentialFilter || undefined,
    onDeleteSuccess: () => {
      navigate(listHref)
    },
  })

  const handleTest = useCallback(
    (id: string): void => {
      testMutation.mutate({ id, teamId: teamId !== '' ? teamId : undefined })
    },
    [testMutation, teamId]
  )

  const handleSave = useCallback(
    (id: string, body: GatewayModelUpdateBody): void => {
      updateModelMutation.mutate({ id, body })
    },
    [updateModelMutation]
  )

  const handleResyncCapabilities = useCallback(
    (id: string): void => {
      updateModelMutation.mutate({ id, body: { resync_capabilities: true } })
    },
    [updateModelMutation]
  )

  const handleToggleEnabled = useCallback(
    (id: string, enabled: boolean): void => {
      updateModelMutation.mutate({ id, body: { enabled } })
    },
    [updateModelMutation]
  )

  const handleDelete = useCallback((_id: string): void => {
    setDeleteOpen(true)
  }, [])

  const handleConfirmDelete = useCallback((): void => {
    setDeleteOpen(false)
    deleteModelMutation.mutate({ id: modelId })
  }, [modelId, deleteModelMutation])

  const isResyncing =
    updateModelMutation.isPending && updateModelMutation.variables.body.resync_capabilities === true
  const isSaving = updateModelMutation.isPending && !isResyncing

  if (isLoading || (trySystemFallback && systemFallbackLoading && !model)) {
    return <ModelDetailLoadingState />
  }

  if (!model) {
    return <ModelDetailNotFoundState />
  }

  return (
    <>
      <ModelInspector
        model={model}
        credentials={credentials ?? []}
        routes={routes ?? []}
        usageDays={usageDays}
        usageRow={usageByRouteName.get(model.name)}
        usageLoading={usageLoading}
        isTesting={testMutation.isPending && testMutation.variables.id === model.id}
        isSaving={isSaving}
        isResyncing={isResyncing}
        isDeleting={deleteModelMutation.isPending}
        onTest={handleTest}
        onSave={handleSave}
        onResyncCapabilities={handleResyncCapabilities}
        onToggleEnabled={handleToggleEnabled}
        onDelete={handleDelete}
      />

      <GatewayModelDeleteConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        displayLabel={model.name}
        scope="team"
        pending={deleteModelMutation.isPending}
        onConfirm={handleConfirmDelete}
      />
    </>
  )
}
