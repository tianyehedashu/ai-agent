import { useCallback, useMemo, useRef, useState } from 'react'

import { useQueryClient } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import {
  fetchAllGatewayModelPages,
  fetchAllManagedTeamModelPages,
  type GatewayModel,
  type GatewayModelBatchDeleteFailureItem,
  type GatewayModelListQuery,
  type ListManagedTeamModelsParams,
  type ModelConnectivitySummary,
} from '@/api/gateway/models'
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
  groupModelIdsByTeamId,
  invalidateGatewayModelAliasDependents,
  invalidateGatewayModelCaches,
  resolveGatewayModelTeamId,
  runChunkedBatchDeleteByTeamIds,
  runChunkedBatchResyncByTeamIds,
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

  const scope = options.scope
  const singleTeamId = options.scope === 'single-team' ? options.teamId : undefined

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

  const listQueryBaseRef = useRef(options.listQueryBase)
  listQueryBaseRef.current = options.listQueryBase

  const canShowBatchOpsRef = useRef(canShowBatchOps)
  canShowBatchOpsRef.current = canShowBatchOps

  const canDeleteModelRef = useRef(canDeleteModel)
  canDeleteModelRef.current = canDeleteModel

  const canResyncModelRef = useRef(canResyncModel)
  canResyncModelRef.current = canResyncModel

  const canManageModelRef = useRef(canManageModel)
  canManageModelRef.current = canManageModel

  const onBatchDeleteSucceededRef = useRef(onBatchDeleteSucceeded)
  onBatchDeleteSucceededRef.current = onBatchDeleteSucceeded

  const teamByModelIdRef = useRef<Map<string, string>>(new Map())

  const registryItemsById = useMemo(() => {
    const map = new Map<string, GatewayModel>()
    for (const model of registryItems) {
      map.set(model.id, model)
    }
    return map
  }, [registryItems])

  const populateTeamByModelId = useCallback((models: readonly GatewayModel[]): void => {
    for (const model of models) {
      const teamId = resolveGatewayModelTeamId(model)
      if (teamId) {
        teamByModelIdRef.current.set(model.id, teamId)
      }
    }
  }, [])

  const resolveTeamIdForModel = useCallback(
    (id: string): string | null => {
      const cached = teamByModelIdRef.current.get(id)
      if (cached) return cached
      const fromPage = registryItemsById.get(id)
      if (!fromPage) return null
      return resolveGatewayModelTeamId(fromPage)
    },
    [registryItemsById]
  )

  const fetchAllFiltered = useCallback(async (): Promise<GatewayModel[]> => {
    const listQueryBase = listQueryBaseRef.current
    if (scope === 'single-team' && singleTeamId) {
      return fetchAllGatewayModelPages(singleTeamId, listQueryBase)
    }
    return fetchAllManagedTeamModelPages(listQueryBase)
  }, [scope, singleTeamId])

  const invalidateModelCaches = useCallback((): void => {
    invalidateGatewayModelCaches(queryClient, {
      credentialId,
      usageSummary: true,
    })
  }, [queryClient, credentialId])

  const handleBatchDeleteComplete = useCallback(
    (result: BatchDeleteChunkResult): void => {
      invalidateGatewayModelCaches(queryClient, {
        credentialId,
        usageSummary: true,
      })
      invalidateGatewayModelAliasDependents(queryClient)
      setDeleteFailedOpen(false)
      onBatchDeleteSucceededRef.current?.(result.succeeded)
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
    [queryClient, credentialId, toast]
  )

  const deleteChunk = useCallback(
    async (chunk: string[]): Promise<BatchDeleteChunkResult> => {
      if (scope === 'single-team' && singleTeamId) {
        return gatewayApi.batchDeleteModels(singleTeamId, chunk)
      }
      const idsByTeam = groupModelIdsByTeamId(chunk, resolveTeamIdForModel)
      return runChunkedBatchDeleteByTeamIds(idsByTeam, (teamId, teamChunk) =>
        gatewayApi.batchDeleteModels(teamId, teamChunk)
      )
    },
    [scope, singleTeamId, resolveTeamIdForModel]
  )

  const { batchDeleting, runBatchDelete } = useChunkedModelBatchDelete({
    deleteChunk,
    onComplete: handleBatchDeleteComplete,
  })

  const handleBatchResyncComplete = useCallback(
    (result: BatchResyncChunkResult): void => {
      invalidateModelCaches()
      if (result.failed.length > 0) {
        setBatchFailedDialogTitle('部分模型未能同步能力')
        setBatchFailedDialogDescription('以下条目未同步成功，其余已处理。')
        setBatchFailedItems(result.failed)
        setBatchFailedOpen(true)
      }
    },
    [invalidateModelCaches]
  )

  const resyncChunk = useCallback(
    async (chunk: string[]): Promise<BatchResyncChunkResult> => {
      if (scope === 'single-team' && singleTeamId) {
        return gatewayApi.batchResyncCapabilities(singleTeamId, chunk)
      }
      const idsByTeam = groupModelIdsByTeamId(chunk, resolveTeamIdForModel)
      return runChunkedBatchResyncByTeamIds(idsByTeam, (teamId, teamChunk) =>
        gatewayApi.batchResyncCapabilities(teamId, teamChunk)
      )
    },
    [scope, singleTeamId, resolveTeamIdForModel]
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
      if (scope === 'single-team' && singleTeamId) {
        return gatewayApi.testModel(singleTeamId, id)
      }
      const teamId = resolveTeamIdForModel(id)
      if (!teamId) {
        return Promise.reject(new Error(`无法解析模型 ${id} 的团队归属`))
      }
      return gatewayApi.testModel(teamId, id)
    },
    [scope, singleTeamId, resolveTeamIdForModel]
  )

  const handleBatchTestComplete = useCallback(
    (failed: readonly string[]) => {
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
    [toast]
  )

  const {
    state: batchTestState,
    start: startBatchTest,
    retestFailed,
  } = useConnectivityBatchTest({
    testById,
    onItemComplete: onBatchItemComplete,
    invalidate: invalidateModelCaches,
    onComplete: handleBatchTestComplete,
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

  const filterTestableForBatch = useCallback((models: readonly GatewayModel[]) => {
    if (!canShowBatchOpsRef.current) return []
    return filterManageableTestableModels(models, canManageModelRef.current)
  }, [])

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
      const resyncable = filterResyncableCapabilityModels(all, canResyncModelRef.current)
      if (resyncable.length === 0) return
      populateTeamByModelId(resyncable)
      runBatchResync(resyncable.map((m) => m.id))
    })()
  }, [fetchAllFiltered, populateTeamByModelId, runBatchResync])

  const handleResyncSelected = useCallback(
    (items: readonly GatewayModel[]): void => {
      const resyncable = filterResyncableCapabilityModels(items, canResyncModelRef.current)
      if (resyncable.length === 0) return
      populateTeamByModelId(resyncable)
      runBatchResync(resyncable.map((m) => m.id))
    },
    [populateTeamByModelId, runBatchResync]
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
      const listQueryBase = listQueryBaseRef.current
      const all =
        scope === 'single-team' && singleTeamId
          ? await fetchAllGatewayModelPages(singleTeamId, {
              ...listQueryBase,
              connectivity: 'failed',
            })
          : await fetchAllManagedTeamModelPages({
              ...listQueryBase,
              connectivity: 'failed',
            })
      const deletable = filterDeletableFailedModels(all, canDeleteModelRef.current)
      if (deletable.length === 0) return
      populateTeamByModelId(deletable)
      runBatchDelete(deletable.map((m) => m.id))
    })()
  }, [scope, singleTeamId, populateTeamByModelId, runBatchDelete])

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
