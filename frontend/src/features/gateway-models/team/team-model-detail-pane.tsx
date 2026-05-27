import { useCallback, useMemo, useState } from 'react'

import { useQuery } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { gatewayApi, type GatewayModelUpdateBody } from '@/api/gateway'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import type { UsagePeriodDays } from '@/features/gateway-models/constants'
import { parseModelsScopeTab } from '@/features/gateway-models/constants'
import { useGatewayModelMutations } from '@/features/gateway-models/hooks/use-gateway-model-mutations'
import {
  systemModelsFilteredHref,
  teamModelsFilteredHref,
  teamModelsIndexHref,
} from '@/features/gateway-models/paths'
import { resolveTeamModelsRegistryScope } from '@/features/gateway-models/utils'
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

  const resolvedModel = primaryModel ?? systemFallbackModel ?? null
  const resolvedRouteName = resolvedModel?.name ?? ''

  const listHref =
    credentialFilter !== ''
      ? scopeTab === 'system'
        ? systemModelsFilteredHref(teamId, credentialFilter)
        : teamModelsFilteredHref(teamId, credentialFilter)
      : scopeTab === 'system'
        ? systemModelsFilteredHref(teamId)
        : teamModelsIndexHref(teamId)

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

  const usageByRouteName = useMemo(() => {
    const m = new Map<string, NonNullable<typeof usageSummary>['items'][number]>()
    for (const row of usageSummary?.items ?? []) {
      m.set(row.route_name, row)
    }
    return m
  }, [usageSummary])

  const model = resolvedModel

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
    <>
      <ModelInspector
        model={model}
        credentials={credentials ?? []}
        routes={routes ?? []}
        usageDays={usageDays}
        usageRow={usageByRouteName.get(model.name)}
        usageLoading={usageLoading}
        isTesting={testMutation.isPending && testMutation.variables.id === model.id}
        isSaving={updateModelMutation.isPending}
        isDeleting={deleteModelMutation.isPending}
        onTest={handleTest}
        onSave={handleSave}
        onResyncCapabilities={handleResyncCapabilities}
        onToggleEnabled={handleToggleEnabled}
        onDelete={handleDelete}
      />

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除模型</AlertDialogTitle>
            <AlertDialogDescription>
              {`确定删除模型「${model.name}」？将同步更新虚拟 Key / 路由中的模型白名单，并清理相关授权与预算行。此操作不可撤销。`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteModelMutation.isPending}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteModelMutation.isPending}
              onClick={handleConfirmDelete}
            >
              {deleteModelMutation.isPending ? '删除中…' : '确认删除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
