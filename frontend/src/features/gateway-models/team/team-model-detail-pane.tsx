import { useCallback, useMemo, useState } from 'react'

import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'

import { gatewayApi, type GatewayModelUpdateBody } from '@/api/gateway'
import type { UsagePeriodDays } from '@/features/gateway-models/constants'
import { useGatewayModelMutations } from '@/features/gateway-models/hooks/use-gateway-model-mutations'
import { gatewayModelsListQueryKey } from '@/features/gateway-models/utils'

import { ModelInspector } from './model-inspector'

interface TeamModelDetailPaneProps {
  modelId: string
}

export function TeamModelDetailPane({ modelId }: TeamModelDetailPaneProps): React.JSX.Element {
  const [searchParams] = useSearchParams()
  const credentialFilter = searchParams.get('credentialId') ?? ''
  const [usageDays] = useState<UsagePeriodDays>(7)

  const { data: items, isLoading } = useQuery({
    queryKey: gatewayModelsListQueryKey('', credentialFilter),
    queryFn: () =>
      gatewayApi.listModels({
        ...(credentialFilter ? { credential_id: credentialFilter } : {}),
      }),
  })

  const { data: usageSummary, isLoading: usageLoading } = useQuery({
    queryKey: ['gateway', 'models', 'usage-summary', '', usageDays],
    queryFn: () => gatewayApi.modelsUsageSummary({ days: usageDays }),
  })

  const { data: routes } = useQuery({
    queryKey: ['gateway', 'routes'],
    queryFn: () => gatewayApi.listRoutes(),
    enabled: modelId !== '',
  })

  const { data: credentials } = useQuery({
    queryKey: ['gateway', 'credentials'],
    queryFn: () => gatewayApi.listCredentials(),
  })

  const usageByRouteName = useMemo(() => {
    const m = new Map<string, NonNullable<typeof usageSummary>['items'][number]>()
    for (const row of usageSummary?.items ?? []) {
      m.set(row.route_name, row)
    }
    return m
  }, [usageSummary])

  const model = useMemo(() => (items ?? []).find((m) => m.id === modelId) ?? null, [items, modelId])

  const { updateModelMutation, testMutation } = useGatewayModelMutations({
    credentialId: credentialFilter || undefined,
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

  if (isLoading) {
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
      onTest={handleTest}
      onSave={handleSave}
      onToggleEnabled={handleToggleEnabled}
    />
  )
}
