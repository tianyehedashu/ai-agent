import { useCallback, useMemo, useState } from 'react'

import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import { gatewayApi } from '@/api/gateway'
import type { PersonalGatewayModelUpdateBody } from '@/api/gateway/my-models'
import type { UsagePeriodDays } from '@/features/gateway-models/constants'
import { GatewayModelDeleteConfirmDialog } from '@/features/gateway-models/detail/gateway-model-delete-confirm-dialog'
import {
  ModelDetailLoadingState,
  ModelDetailNotFoundState,
} from '@/features/gateway-models/detail/model-detail-states'
import { ModelInspector } from '@/features/gateway-models/detail/model-inspector'
import { usePersonalModelMutations } from '@/features/gateway-models/hooks/use-personal-model-mutations'
import { personalModelsIndexHref } from '@/features/gateway-models/paths'
import {
  personalModelInspectorContext,
  personalModelToInspectorModel,
} from '@/features/gateway-models/personal/personal-model-inspector-adapter'
import { indexUsageByRouteName } from '@/features/gateway-models/usage-summary-index'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'

interface PersonalModelDetailPaneProps {
  modelId: string
}

export function PersonalModelDetailPane({
  modelId,
}: PersonalModelDetailPaneProps): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const navigate = useNavigate()
  const [usageDays] = useState<UsagePeriodDays>(7)
  const [deleteOpen, setDeleteOpen] = useState(false)

  const { data: model, isLoading } = useQuery({
    queryKey: ['gateway', 'my-models', modelId],
    queryFn: () => gatewayApi.getMyModel(modelId),
    enabled: modelId !== '',
  })

  const { data: credentials = [] } = useQuery({
    queryKey: ['gateway', 'my-credentials'],
    queryFn: () => gatewayApi.listMyCredentials(),
  })

  const routeName = model?.name ?? ''

  const { data: usageSummary, isLoading: usageLoading } = useQuery({
    queryKey: ['gateway', 'my-models', 'usage-summary', routeName, usageDays],
    queryFn: () =>
      gatewayApi.myModelsUsageSummary({
        days: usageDays,
        route_names: [routeName],
      }),
    enabled: routeName !== '',
  })

  const usageByRouteName = useMemo(
    () => indexUsageByRouteName(usageSummary?.items),
    [usageSummary?.items]
  )

  const inspectorModel = useMemo(
    () => (model ? personalModelToInspectorModel(model) : null),
    [model]
  )

  const personalContext = useMemo(
    () => (model ? personalModelInspectorContext(model) : undefined),
    [model]
  )

  const listHref = personalModelsIndexHref(teamId)

  const { updateMutation, deleteMutation, testMutation } = usePersonalModelMutations({
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

  const handleSavePersonal = useCallback(
    (id: string, body: PersonalGatewayModelUpdateBody): void => {
      updateMutation.mutate({ id, body })
    },
    [updateMutation]
  )

  const handleResyncCapabilities = useCallback(
    (id: string): void => {
      updateMutation.mutate({ id, body: { resync_capabilities: true } })
    },
    [updateMutation]
  )

  const handleToggleEnabled = useCallback(
    (id: string, enabled: boolean): void => {
      updateMutation.mutate({ id, body: { is_active: enabled } })
    },
    [updateMutation]
  )

  const handleDelete = useCallback((_id: string): void => {
    setDeleteOpen(true)
  }, [])

  const handleConfirmDelete = useCallback((): void => {
    setDeleteOpen(false)
    deleteMutation.mutate(modelId)
  }, [modelId, deleteMutation])

  const isResyncing =
    updateMutation.isPending && updateMutation.variables.body.resync_capabilities === true
  const isSaving = updateMutation.isPending && !isResyncing

  if (isLoading) {
    return <ModelDetailLoadingState />
  }

  if (!model || !inspectorModel || !personalContext) {
    return <ModelDetailNotFoundState />
  }

  return (
    <>
      <ModelInspector
        scope="personal"
        personalContext={personalContext}
        model={inspectorModel}
        credentials={credentials}
        routes={[]}
        usageDays={usageDays}
        usageRow={usageByRouteName.get(model.name)}
        usageLoading={usageLoading}
        isTesting={testMutation.isPending}
        isSaving={isSaving}
        isResyncing={isResyncing}
        isDeleting={deleteMutation.isPending}
        onTest={handleTest}
        onSavePersonal={handleSavePersonal}
        onResyncCapabilities={handleResyncCapabilities}
        onToggleEnabled={handleToggleEnabled}
        onDelete={handleDelete}
      />

      <GatewayModelDeleteConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        displayLabel={model.display_name}
        scope="personal"
        pending={deleteMutation.isPending}
        onConfirm={handleConfirmDelete}
      />
    </>
  )
}
