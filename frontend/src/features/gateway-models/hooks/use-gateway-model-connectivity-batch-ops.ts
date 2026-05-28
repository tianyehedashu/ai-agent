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
import {
  fetchAllPersonalGatewayModels,
  type PersonalGatewayModel,
  type PersonalModelListQuery,
} from '@/api/gateway/my-models'
import { useChunkedModelBatchDelete } from '@/features/gateway-models/hooks/use-chunked-model-batch-delete'
import { useChunkedModelBatchResync } from '@/features/gateway-models/hooks/use-chunked-model-batch-resync'
import { useConnectivityBatchTest } from '@/features/gateway-models/hooks/use-connectivity-batch-test'
import { invalidatePersonalModelCaches } from '@/features/gateway-models/hooks/use-personal-model-mutations'
import {
  createBatchConnectivityCachePatcher,
  filterDeletableFailedModels,
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

interface PersonalConnectivityBatchOps {
  scope: 'personal'
  registryItems: readonly PersonalGatewayModel[]
  connectivitySummary?: ModelConnectivitySummary
  listTotal?: number
  listQueryBase: Omit<PersonalModelListQuery, 'page' | 'page_size' | 'connectivity'>
  canShowBatchOps: boolean
  canDeleteModel: (model: PersonalGatewayModel) => boolean
  canResyncModel: (model: PersonalGatewayModel) => boolean
  canManageModel: (model: PersonalGatewayModel) => boolean
  onBatchDeleteSucceeded?: (succeededIds: readonly string[]) => void
}

export type UseGatewayModelConnectivityBatchOpsOptions =
  | SingleTeamConnectivityBatchOps
  | ManagedTeamsConnectivityBatchOps
  | PersonalConnectivityBatchOps

type BatchOpsRegistryItem = GatewayModel | PersonalGatewayModel

export function useGatewayModelConnectivityBatchOps(
  options: UseGatewayModelConnectivityBatchOpsOptions
): {
  batchTestState: ReturnType<typeof useConnectivityBatchTest>['state']
  batchBusy: boolean
  batchTesting: boolean
  batchDeleting: boolean
  batchResyncing: boolean
  testableItems: BatchOpsRegistryItem[]
  untestedTestableItems: BatchOpsRegistryItem[]
  failedDeletableCount: number
  failedDeletableModels: BatchOpsRegistryItem[]
  deleteFailedLabel: string
  handleTestAll: () => void
  handleTestUntested: () => void
  handleTestSelected: (items: readonly BatchOpsRegistryItem[]) => void
  handleResyncAll: () => void
  handleResyncSelected: (items: readonly BatchOpsRegistryItem[]) => void
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
  formatBatchDeleteLabel: (models: readonly BatchOpsRegistryItem[]) => string
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
  const isPersonalScope = options.scope === 'personal'

  const {
    registryItems,
    connectivitySummary,
    canShowBatchOps,
    canDeleteModel,
    canResyncModel,
    canManageModel,
    onBatchDeleteSucceeded,
  } = options

  const credentialId = options.scope === 'personal' ? undefined : options.credentialId

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
    const map = new Map<string, BatchOpsRegistryItem>()
    for (const model of registryItems) {
      map.set(model.id, model)
    }
    return map
  }, [registryItems])

  const populateTeamByModelId = useCallback(
    (models: readonly BatchOpsRegistryItem[]): void => {
      if (isPersonalScope) return
      for (const model of models) {
        const teamId = resolveGatewayModelTeamId(model as GatewayModel)
        if (teamId) {
          teamByModelIdRef.current.set(model.id, teamId)
        }
      }
    },
    [isPersonalScope]
  )

  const resolveTeamIdForModel = useCallback(
    (id: string): string | null => {
      const cached = teamByModelIdRef.current.get(id)
      if (cached) return cached
      const fromPage = registryItemsById.get(id)
      if (!fromPage || isPersonalScope) return null
      return resolveGatewayModelTeamId(fromPage as GatewayModel)
    },
    [registryItemsById, isPersonalScope]
  )

  const fetchAllFiltered = useCallback(async (): Promise<BatchOpsRegistryItem[]> => {
    const listQueryBase = listQueryBaseRef.current
    if (isPersonalScope) {
      return fetchAllPersonalGatewayModels(listQueryBase as PersonalModelListQuery)
    }
    if (scope === 'single-team' && singleTeamId) {
      return fetchAllGatewayModelPages(singleTeamId, listQueryBase as GatewayModelListQuery)
    }
    return fetchAllManagedTeamModelPages(listQueryBase as ListManagedTeamModelsParams)
  }, [scope, singleTeamId, isPersonalScope])

  const invalidateModelCaches = useCallback((): void => {
    if (isPersonalScope) {
      invalidatePersonalModelCaches(queryClient)
      return
    }
    invalidateGatewayModelCaches(queryClient, {
      credentialId,
      usageSummary: true,
    })
  }, [queryClient, credentialId, isPersonalScope])

  const handleBatchDeleteComplete = useCallback(
    (result: BatchDeleteChunkResult): void => {
      if (isPersonalScope) {
        invalidatePersonalModelCaches(queryClient)
      } else {
        invalidateGatewayModelCaches(queryClient, {
          credentialId,
          usageSummary: true,
        })
        invalidateGatewayModelAliasDependents(queryClient)
      }
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
    [queryClient, credentialId, toast, isPersonalScope]
  )

  const deleteChunk = useCallback(
    async (chunk: string[]): Promise<BatchDeleteChunkResult> => {
      if (isPersonalScope) {
        return gatewayApi.batchDeleteMyModels(chunk)
      }
      if (scope === 'single-team' && singleTeamId) {
        return gatewayApi.batchDeleteModels(singleTeamId, chunk)
      }
      const idsByTeam = groupModelIdsByTeamId(chunk, resolveTeamIdForModel)
      return runChunkedBatchDeleteByTeamIds(idsByTeam, (teamId, teamChunk) =>
        gatewayApi.batchDeleteModels(teamId, teamChunk)
      )
    },
    [scope, singleTeamId, resolveTeamIdForModel, isPersonalScope]
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
      if (isPersonalScope) {
        return gatewayApi.batchResyncMyModels(chunk)
      }
      if (scope === 'single-team' && singleTeamId) {
        return gatewayApi.batchResyncCapabilities(singleTeamId, chunk)
      }
      const idsByTeam = groupModelIdsByTeamId(chunk, resolveTeamIdForModel)
      return runChunkedBatchResyncByTeamIds(idsByTeam, (teamId, teamChunk) =>
        gatewayApi.batchResyncCapabilities(teamId, teamChunk)
      )
    },
    [scope, singleTeamId, resolveTeamIdForModel, isPersonalScope]
  )

  const { batchResyncing, runBatchResync } = useChunkedModelBatchResync({
    resyncChunk,
    onComplete: handleBatchResyncComplete,
  })

  const onBatchItemComplete = useMemo(
    () => createBatchConnectivityCachePatcher(queryClient, isPersonalScope ? 'personal' : 'team'),
    [queryClient, isPersonalScope]
  )

  const testById = useCallback(
    async (id: string) => {
      if (isPersonalScope) {
        return gatewayApi.testMyModel(id)
      }
      if (scope === 'single-team' && singleTeamId) {
        return gatewayApi.testModel(singleTeamId, id)
      }
      const teamId = resolveTeamIdForModel(id)
      if (!teamId) {
        return Promise.reject(new Error(`无法解析模型 ${id} 的团队归属`))
      }
      return gatewayApi.testModel(teamId, id)
    },
    [scope, singleTeamId, resolveTeamIdForModel, isPersonalScope]
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

  const filterTestableForBatch = useCallback((models: readonly BatchOpsRegistryItem[]) => {
    if (!canShowBatchOpsRef.current) return []
    const canManage = canManageModelRef.current as (model: BatchOpsRegistryItem) => boolean
    return filterTestableConnectivityModels(models).filter(canManage)
  }, [])

  const filterResyncableForBatch = useCallback((models: readonly BatchOpsRegistryItem[]) => {
    const canResync = canResyncModelRef.current as (model: BatchOpsRegistryItem) => boolean
    return models.filter(canResync)
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
    (items: readonly BatchOpsRegistryItem[]): void => {
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
      const resyncable = filterResyncableForBatch(all)
      if (resyncable.length === 0) return
      populateTeamByModelId(resyncable)
      runBatchResync(resyncable.map((m) => m.id))
    })()
  }, [fetchAllFiltered, populateTeamByModelId, runBatchResync, filterResyncableForBatch])

  const handleResyncSelected = useCallback(
    (items: readonly BatchOpsRegistryItem[]): void => {
      const resyncable = filterResyncableForBatch(items)
      if (resyncable.length === 0) return
      populateTeamByModelId(resyncable)
      runBatchResync(resyncable.map((m) => m.id))
    },
    [populateTeamByModelId, runBatchResync, filterResyncableForBatch]
  )

  const failedDeletableModels = useMemo(() => {
    const canDelete = canDeleteModel as (model: BatchOpsRegistryItem) => boolean
    return filterDeletableFailedModels(registryItems as readonly BatchOpsRegistryItem[], canDelete)
  }, [registryItems, canDeleteModel])

  const failedDeletableCount = connectivitySummary?.failed ?? failedDeletableModels.length

  const deleteFailedLabel = useMemo((): string => {
    const labels = failedDeletableModels.map((m) => ('display_name' in m ? m.display_name : m.name))
    return formatDeleteFailedConfirmLabel(failedDeletableCount, labels)
  }, [failedDeletableCount, failedDeletableModels])

  const handleDeleteFailed = useCallback((): void => {
    if (failedDeletableCount === 0) return
    setDeleteFailedOpen(true)
  }, [failedDeletableCount])

  const handleConfirmDeleteFailed = useCallback((): void => {
    void (async () => {
      const listQueryBase = listQueryBaseRef.current
      const all = isPersonalScope
        ? await fetchAllPersonalGatewayModels({
            ...(listQueryBase as PersonalModelListQuery),
            connectivity: 'failed',
          })
        : scope === 'single-team' && singleTeamId
          ? await fetchAllGatewayModelPages(singleTeamId, {
              ...(listQueryBase as GatewayModelListQuery),
              connectivity: 'failed',
            })
          : await fetchAllManagedTeamModelPages({
              ...(listQueryBase as ListManagedTeamModelsParams),
              connectivity: 'failed',
            })
      const canDelete = canDeleteModelRef.current as (model: BatchOpsRegistryItem) => boolean
      const deletable = filterDeletableFailedModels(
        all as readonly BatchOpsRegistryItem[],
        canDelete
      )
      if (deletable.length === 0) return
      populateTeamByModelId(deletable)
      runBatchDelete(deletable.map((m) => m.id))
    })()
  }, [scope, singleTeamId, populateTeamByModelId, runBatchDelete, isPersonalScope])

  const testableItems = useMemo(
    () => filterTestableConnectivityModels(registryItems as readonly BatchOpsRegistryItem[]),
    [registryItems]
  )

  const untestedTestableItems = useMemo(
    () => filterUntestedConnectivityModels(registryItems as readonly BatchOpsRegistryItem[]),
    [registryItems]
  )

  const batchTesting = batchTestState.running
  const batchBusy = batchTesting || batchResyncing || batchDeleting

  const formatBatchDeleteLabel = useCallback((models: readonly BatchOpsRegistryItem[]): string => {
    const labels = models.map((m) => ('display_name' in m ? m.display_name : m.name))
    return formatBatchDeleteConfirmLabel(labels)
  }, [])

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

/** @alias useGatewayModelConnectivityBatchOps */
export const useGatewayModelListBatchOps = useGatewayModelConnectivityBatchOps
