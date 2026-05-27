import { useCallback, useMemo, useRef, useState } from 'react'

import { useQueryClient } from '@tanstack/react-query'

import {
  fetchAllGatewayModelPages,
  fetchAllManagedTeamModelPages,
  gatewayApi,
  type GatewayModel,
  type GatewayModelBatchDeleteFailureItem,
  type GatewayModelListQuery,
  type ListManagedTeamModelsParams,
  type ModelConnectivitySummary,
} from '@/api/gateway'
import { useChunkedModelBatchDelete } from '@/features/gateway-models/hooks/use-chunked-model-batch-delete'
import { useChunkedModelBatchResync } from '@/features/gateway-models/hooks/use-chunked-model-batch-resync'
import { useConnectivityBatchTest } from '@/features/gateway-models/hooks/use-connectivity-batch-test'
import {
  createBatchConnectivityCachePatcher,
  filterDeletableFailedModels,
  filterManageableTestableModels,
  filterResyncableCapabilityModels,
  filterTestableConnectivityModels,
  filterUntestedConnectivityModels,
  formatBatchDeleteConfirmLabel,
  formatDeleteFailedConfirmLabel,
  invalidateGatewayModelAliasDependents,
  invalidateGatewayModelCaches,
  resolveGatewayModelTeamId,
  runChunkedBatchDeleteByTeam,
  runChunkedBatchResyncByTeam,
  type BatchDeleteChunkResult,
  type BatchResyncChunkResult,
} from '@/features/gateway-models/utils'
import { useToast } from '@/hooks/use-toast'

interface ConnectivityBatchOpsBase {
  registryItems: readonly GatewayModel[]
  connectivitySummary?: ModelConnectivitySummary
  listTotal?: number
  credentialId?: string
  canShowBatchOps: boolean
  canDeleteModel: (model: GatewayModel) => boolean
  canResyncModel: (model: GatewayModel) => boolean
  canManageModel: (model: GatewayModel) => boolean
  /** 批量删除成功后从勾选集移除 succeeded ids */
  onBatchDeleteSucceeded?: (succeededIds: readonly string[]) => void
}

interface SingleTeamConnectivityBatchOps extends ConnectivityBatchOpsBase {
  scope: 'single-team'
  teamId: string
  listQueryBase: Omit<GatewayModelListQuery, 'page' | 'page_size' | 'connectivity'>
}

interface ManagedTeamsConnectivityBatchOps extends ConnectivityBatchOpsBase {
  scope: 'managed-teams'
  listQueryBase: Omit<ListManagedTeamModelsParams, 'page' | 'page_size' | 'connectivity'>
}

export type UseGatewayModelConnectivityBatchOpsOptions =
  | SingleTeamConnectivityBatchOps
  | ManagedTeamsConnectivityBatchOps

export function useGatewayModelConnectivityBatchOps(
  options: UseGatewayModelConnectivityBatchOpsOptions
): {
  batchTestState: ReturnType<typeof useConnectivityBatchTest>['state']
  batchBusy: boolean
  batchTesting: boolean
  batchDeleting: boolean
  batchResyncing: boolean
  testableItems: GatewayModel[]
  untestedTestableItems: GatewayModel[]
  failedDeletableCount: number
  failedDeletableModels: GatewayModel[]
  deleteFailedLabel: string
  handleTestAll: () => void
  handleTestUntested: () => void
  handleTestSelected: (items: readonly GatewayModel[]) => void
  handleResyncAll: () => void
  handleResyncSelected: (items: readonly GatewayModel[]) => void
  handleDeleteFailed: () => void
  handleConfirmDeleteFailed: () => void
  runBatchDelete: (ids: readonly string[]) => void
  retestFailed: () => void
  scrollToFirstFailed: () => void
  deleteFailedOpen: boolean
  setDeleteFailedOpen: (open: boolean) => void
  batchFailedOpen: boolean
  setBatchFailedOpen: (open: boolean) => void
  batchFailedItems: GatewayModelBatchDeleteFailureItem[]
  batchFailedDialogTitle: string
  batchFailedDialogDescription: string
  formatBatchDeleteLabel: (models: readonly GatewayModel[]) => string
} {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const [deleteFailedOpen, setDeleteFailedOpen] = useState(false)
  const [batchFailedOpen, setBatchFailedOpen] = useState(false)
  const [batchFailedItems, setBatchFailedItems] = useState<GatewayModelBatchDeleteFailureItem[]>([])
  const [batchFailedDialogTitle, setBatchFailedDialogTitle] = useState('部分模型未能删除')
  const [batchFailedDialogDescription, setBatchFailedDialogDescription] =
    useState('以下条目未删除成功，其余已处理。')

  const {
    registryItems,
    connectivitySummary,
    credentialId,
    canShowBatchOps,
    canDeleteModel,
    canResyncModel,
    canManageModel,
    onBatchDeleteSucceeded,
  } = options

  const teamByModelIdRef = useRef<Map<string, string>>(new Map())

  const populateTeamByModelId = useCallback((models: readonly GatewayModel[]): void => {
    const map = new Map<string, string>()
    for (const model of models) {
      const teamId = resolveGatewayModelTeamId(model)
      if (teamId) map.set(model.id, teamId)
    }
    teamByModelIdRef.current = map
  }, [])

  const resolveTeamIdForModel = useCallback(
    (id: string): string | null => {
      const cached = teamByModelIdRef.current.get(id)
      if (cached) return cached
      const fromPage = registryItems.find((m) => m.id === id)
      if (!fromPage) return null
      return resolveGatewayModelTeamId(fromPage)
    },
    [registryItems]
  )

  const fetchAllFiltered = useCallback(async (): Promise<GatewayModel[]> => {
    if (options.scope === 'single-team') {
      return fetchAllGatewayModelPages(options.teamId, options.listQueryBase)
    }
    return fetchAllManagedTeamModelPages(options.listQueryBase)
  }, [options])

  const handleBatchDeleteComplete = useCallback(
    (result: BatchDeleteChunkResult): void => {
      invalidateGatewayModelCaches(queryClient, {
        credentialId,
        usageSummary: true,
      })
      invalidateGatewayModelAliasDependents(queryClient)
      setDeleteFailedOpen(false)
      onBatchDeleteSucceeded?.(result.succeeded)
      if (result.failed.length > 0) {
        setBatchFailedDialogTitle('部分模型未能删除')
        setBatchFailedDialogDescription('以下条目未删除成功，其余已处理。')
        setBatchFailedItems(result.failed)
        setBatchFailedOpen(true)
      } else if (result.succeeded.length > 0) {
        const cleanupParts: string[] = []
        if (result.grants_removed > 0) {
          cleanupParts.push(`${String(result.grants_removed)} 条授权`)
        }
        if (result.budgets_removed > 0) {
          cleanupParts.push(`${String(result.budgets_removed)} 条预算`)
        }
        const cleanupHint = cleanupParts.length > 0 ? `，已清理 ${cleanupParts.join('、')}` : ''
        toast({
          title: `已删除 ${String(result.succeeded.length)} 个模型${cleanupHint}`,
        })
      }
    },
    [queryClient, credentialId, onBatchDeleteSucceeded, toast]
  )

  const deleteChunk = useCallback(
    async (chunk: string[]): Promise<BatchDeleteChunkResult> => {
      if (options.scope === 'single-team') {
        return gatewayApi.batchDeleteModels(options.teamId, chunk)
      }
      const all = await fetchAllFiltered()
      const models = all.filter((m) => chunk.includes(m.id))
      return runChunkedBatchDeleteByTeam(models, (teamId, teamChunk) =>
        gatewayApi.batchDeleteModels(teamId, teamChunk)
      )
    },
    [options, fetchAllFiltered]
  )

  const { batchDeleting, runBatchDelete } = useChunkedModelBatchDelete({
    deleteChunk,
    onComplete: handleBatchDeleteComplete,
  })

  const handleBatchResyncComplete = useCallback(
    (result: BatchResyncChunkResult): void => {
      invalidateGatewayModelCaches(queryClient, {
        credentialId,
        usageSummary: true,
      })
      if (result.failed.length > 0) {
        setBatchFailedDialogTitle('部分模型未能同步能力')
        setBatchFailedDialogDescription('以下条目未同步成功，其余已处理。')
        setBatchFailedItems(result.failed)
        setBatchFailedOpen(true)
      }
    },
    [queryClient, credentialId]
  )

  const resyncChunk = useCallback(
    async (chunk: string[]): Promise<BatchResyncChunkResult> => {
      if (options.scope === 'single-team') {
        return gatewayApi.batchResyncCapabilities(options.teamId, chunk)
      }
      const all = await fetchAllFiltered()
      const models = all.filter((m) => chunk.includes(m.id))
      return runChunkedBatchResyncByTeam(models, (teamId, teamChunk) =>
        gatewayApi.batchResyncCapabilities(teamId, teamChunk)
      )
    },
    [options, fetchAllFiltered]
  )

  const { batchResyncing, runBatchResync } = useChunkedModelBatchResync({
    resyncChunk,
    onComplete: handleBatchResyncComplete,
  })

  const onBatchItemComplete = useMemo(
    () => createBatchConnectivityCachePatcher(queryClient, 'team'),
    [queryClient]
  )

  const testById = useCallback(
    async (id: string) => {
      if (options.scope === 'single-team') {
        return gatewayApi.testModel(options.teamId, id)
      }
      const teamId = resolveTeamIdForModel(id)
      if (!teamId) {
        return Promise.reject(new Error(`无法解析模型 ${id} 的团队归属`))
      }
      return gatewayApi.testModel(teamId, id)
    },
    [options, resolveTeamIdForModel]
  )

  const {
    state: batchTestState,
    start: startBatchTest,
    retestFailed,
  } = useConnectivityBatchTest({
    testById,
    onItemComplete: onBatchItemComplete,
    invalidate: () => {
      invalidateGatewayModelCaches(queryClient, {
        credentialId,
        usageSummary: true,
      })
    },
    onComplete: (failed) => {
      if (failed.length === 0) {
        toast({ title: '批量测试完成' })
      } else {
        toast({
          variant: 'destructive',
          title: '批量测试完成',
          description: `${String(failed.length)} 个模型探活失败`,
        })
      }
    },
  })

  const batchFailedIdsRef = useRef(batchTestState.failedIds)
  batchFailedIdsRef.current = batchTestState.failedIds

  const scrollToFirstFailed = useCallback((): void => {
    const first = batchFailedIdsRef.current[0]
    if (!first) return
    document
      .querySelector(`[data-connectivity-model-id="${first}"]`)
      ?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [])

  const filterTestableForBatch = useCallback(
    (models: readonly GatewayModel[]) =>
      canShowBatchOps ? filterManageableTestableModels(models, canManageModel) : [],
    [canManageModel, canShowBatchOps]
  )

  const handleTestAll = useCallback((): void => {
    void (async () => {
      const all = await fetchAllFiltered()
      populateTeamByModelId(all)
      const testable = filterTestableForBatch(all)
      if (testable.length === 0) return
      startBatchTest(testable)
    })()
  }, [fetchAllFiltered, filterTestableForBatch, populateTeamByModelId, startBatchTest])

  const handleTestUntested = useCallback((): void => {
    void (async () => {
      const all = await fetchAllFiltered()
      populateTeamByModelId(all)
      const untested = filterUntestedConnectivityModels(all)
      const testable = filterTestableForBatch(untested)
      if (testable.length === 0) return
      startBatchTest(testable)
    })()
  }, [fetchAllFiltered, filterTestableForBatch, populateTeamByModelId, startBatchTest])

  const handleTestSelected = useCallback(
    (items: readonly GatewayModel[]): void => {
      populateTeamByModelId(items)
      const testable = filterTestableForBatch(items)
      if (testable.length === 0) return
      startBatchTest(testable)
    },
    [filterTestableForBatch, populateTeamByModelId, startBatchTest]
  )

  const handleResyncAll = useCallback((): void => {
    void (async () => {
      const all = await fetchAllFiltered()
      const resyncable = filterResyncableCapabilityModels(all, canResyncModel)
      if (resyncable.length === 0) return
      runBatchResync(resyncable.map((m) => m.id))
    })()
  }, [fetchAllFiltered, canResyncModel, runBatchResync])

  const handleResyncSelected = useCallback(
    (items: readonly GatewayModel[]): void => {
      const resyncable = filterResyncableCapabilityModels(items, canResyncModel)
      if (resyncable.length === 0) return
      runBatchResync(resyncable.map((m) => m.id))
    },
    [canResyncModel, runBatchResync]
  )

  const failedDeletableModels = useMemo(
    () => filterDeletableFailedModels(registryItems, canDeleteModel),
    [registryItems, canDeleteModel]
  )

  const failedDeletableCount = connectivitySummary?.failed ?? failedDeletableModels.length

  const deleteFailedLabel = useMemo(
    (): string =>
      formatDeleteFailedConfirmLabel(
        failedDeletableCount,
        failedDeletableModels.map((m) => m.name)
      ),
    [failedDeletableCount, failedDeletableModels]
  )

  const handleDeleteFailed = useCallback((): void => {
    if (failedDeletableCount === 0) return
    setDeleteFailedOpen(true)
  }, [failedDeletableCount])

  const handleConfirmDeleteFailed = useCallback((): void => {
    void (async () => {
      const all =
        options.scope === 'single-team'
          ? await fetchAllGatewayModelPages(options.teamId, {
              ...options.listQueryBase,
              connectivity: 'failed',
            })
          : await fetchAllManagedTeamModelPages({
              ...options.listQueryBase,
              connectivity: 'failed',
            })
      const deletable = filterDeletableFailedModels(all, canDeleteModel)
      if (deletable.length === 0) return
      runBatchDelete(deletable.map((m) => m.id))
    })()
  }, [options, canDeleteModel, runBatchDelete])

  const testableItems = useMemo(
    () => filterTestableConnectivityModels(registryItems),
    [registryItems]
  )

  const untestedTestableItems = useMemo(
    () => filterUntestedConnectivityModels(registryItems),
    [registryItems]
  )

  const batchTesting = batchTestState.running
  const batchBusy = batchTesting || batchResyncing || batchDeleting

  const formatBatchDeleteLabel = useCallback(
    (models: readonly GatewayModel[]): string =>
      formatBatchDeleteConfirmLabel(models.map((m) => m.name)),
    []
  )

  return {
    batchTestState,
    batchBusy,
    batchTesting,
    batchDeleting,
    batchResyncing,
    testableItems,
    untestedTestableItems,
    failedDeletableCount,
    failedDeletableModels,
    deleteFailedLabel,
    handleTestAll,
    handleTestUntested,
    handleTestSelected,
    handleResyncAll,
    handleResyncSelected,
    handleDeleteFailed,
    handleConfirmDeleteFailed,
    runBatchDelete,
    retestFailed,
    scrollToFirstFailed,
    deleteFailedOpen,
    setDeleteFailedOpen,
    batchFailedOpen,
    setBatchFailedOpen,
    batchFailedItems,
    batchFailedDialogTitle,
    batchFailedDialogDescription,
    formatBatchDeleteLabel,
  }
}
