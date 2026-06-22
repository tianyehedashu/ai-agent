/**
 * 统一模型列表批量探活 / 同步 / 删除（跨个人 + 团队 + 系统）。
 */

import { useCallback, useMemo, useRef, useState } from 'react'

import { useQueryClient } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import type { GatewayModelBatchDeleteFailureItem } from '@/api/gateway/models'
import { useChunkedModelBatchDelete } from '@/features/gateway-models/hooks/use-chunked-model-batch-delete'
import { useChunkedModelBatchResync } from '@/features/gateway-models/hooks/use-chunked-model-batch-resync'
import { useConnectivityBatchTest } from '@/features/gateway-models/hooks/use-connectivity-batch-test'
import { invalidatePersonalModelCaches } from '@/features/gateway-models/hooks/use-personal-model-mutations'
import type { GatewayModelListItem } from '@/features/gateway-models/list/types'
import { invalidateUnifiedModelsCache } from '@/features/gateway-models/unified/invalidate-unified-models-cache'
import {
  canBatchSelectUnifiedModelItem,
  canDeleteUnifiedModelItem,
  canManageUnifiedModelItem,
  canResyncUnifiedModelItem,
  type UnifiedModelRowPermissionContext,
} from '@/features/gateway-models/unified/unified-model-row-permissions'
import {
  connectivityFieldsFromTestResult,
  filterTestableConnectivityModels,
  filterUntestedConnectivityModels,
  formatBatchDeleteConfirmLabel,
  formatDeleteFailedConfirmLabel,
  groupModelIdsByTeamId,
  invalidateGatewayModelAliasDependents,
  invalidateGatewayModelCaches,
  patchModelConnectivityInCache,
  runChunkedBatchDelete,
  runChunkedBatchDeleteByTeamIds,
  resolveUnifiedModelBatchTeamId,
  runChunkedBatchResyncByTeamIds,
  type BatchDeleteChunkResult,
  type BatchResyncChunkResult,
  type ModelWithConnectivityStatus,
} from '@/features/gateway-models/utils'
import { useToast } from '@/hooks/use-toast'

export interface UseUnifiedModelsBatchOpsOptions {
  filteredEntries: readonly GatewayModelListItem[]
  connectivitySummary: {
    total: number
    success: number
    failed: number
    unknown: number
  }
  permissionCtx: UnifiedModelRowPermissionContext
  canShowBatchOps: boolean
  /** URL 上下文团队；系统模型无 tenant 时批量 test/delete/resync 路由回退 */
  defaultTeamId: string
  onBatchDeleteSucceeded?: (succeededIds: readonly string[]) => void
}

function entryAsConnectivityModel(item: GatewayModelListItem): ModelWithConnectivityStatus {
  const source = item.source as ModelWithConnectivityStatus
  return {
    id: item.id,
    capability: item.capability,
    last_test_status: 'last_test_status' in source ? source.last_test_status : item.lastTestStatus,
  }
}

function mergeDeleteResults(...results: readonly BatchDeleteChunkResult[]): BatchDeleteChunkResult {
  return results.reduce<BatchDeleteChunkResult>(
    (acc, result) => ({
      succeeded: [...acc.succeeded, ...result.succeeded],
      failed: [...acc.failed, ...result.failed],
      grants_removed: acc.grants_removed + result.grants_removed,
      budgets_removed: acc.budgets_removed + result.budgets_removed,
    }),
    { succeeded: [], failed: [], grants_removed: 0, budgets_removed: 0 }
  )
}

function mergeResyncResults(...results: readonly BatchResyncChunkResult[]): BatchResyncChunkResult {
  return results.reduce<BatchResyncChunkResult>(
    (acc, result) => ({
      succeeded: [...acc.succeeded, ...result.succeeded],
      failed: [...acc.failed, ...result.failed],
    }),
    { succeeded: [], failed: [] }
  )
}

export function useUnifiedModelsBatchOps({
  filteredEntries,
  connectivitySummary,
  permissionCtx,
  canShowBatchOps,
  defaultTeamId,
  onBatchDeleteSucceeded,
}: UseUnifiedModelsBatchOpsOptions) {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const [deleteFailedOpen, setDeleteFailedOpen] = useState(false)
  const [batchFailedOpen, setBatchFailedOpen] = useState(false)
  const [batchFailedItems, setBatchFailedItems] = useState<GatewayModelBatchDeleteFailureItem[]>([])
  const [batchFailedDialogTitle, setBatchFailedDialogTitle] = useState('部分模型未能删除')
  const [batchFailedDialogDescription, setBatchFailedDialogDescription] =
    useState('以下条目未删除成功，其余已处理。')

  const entriesById = useMemo(() => {
    const map = new Map<string, GatewayModelListItem>()
    for (const item of filteredEntries) {
      map.set(item.id, item)
    }
    return map
  }, [filteredEntries])

  const entriesByIdRef = useRef(entriesById)
  entriesByIdRef.current = entriesById

  const teamByModelIdRef = useRef<Map<string, string>>(new Map())

  const defaultTeamIdRef = useRef(defaultTeamId)
  defaultTeamIdRef.current = defaultTeamId

  const permissionCtxRef = useRef(permissionCtx)
  permissionCtxRef.current = permissionCtx

  const canShowBatchOpsRef = useRef(canShowBatchOps)
  canShowBatchOpsRef.current = canShowBatchOps

  const onBatchDeleteSucceededRef = useRef(onBatchDeleteSucceeded)
  onBatchDeleteSucceededRef.current = onBatchDeleteSucceeded

  const populateTeamByModelId = useCallback((entries: readonly GatewayModelListItem[]): void => {
    for (const item of entries) {
      const teamId = resolveUnifiedModelBatchTeamId(item, defaultTeamIdRef.current)
      if (teamId) {
        teamByModelIdRef.current.set(item.id, teamId)
      }
    }
  }, [])

  const resolveTeamIdForModel = useCallback((id: string): string | null => {
    const cached = teamByModelIdRef.current.get(id)
    if (cached) return cached
    const item = entriesByIdRef.current.get(id)
    if (!item) return null
    return resolveUnifiedModelBatchTeamId(item, defaultTeamIdRef.current)
  }, [])

  const invalidateModelCaches = useCallback((): void => {
    invalidatePersonalModelCaches(queryClient)
    invalidateGatewayModelCaches(queryClient, { usageSummary: true })
    invalidateUnifiedModelsCache(queryClient)
  }, [queryClient])

  const handleBatchDeleteComplete = useCallback(
    (result: BatchDeleteChunkResult): void => {
      invalidatePersonalModelCaches(queryClient)
      invalidateGatewayModelCaches(queryClient, { usageSummary: true })
      invalidateGatewayModelAliasDependents(queryClient)
      invalidateUnifiedModelsCache(queryClient)
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
    [queryClient, toast]
  )

  const deleteChunk = useCallback(
    async (chunk: string[]): Promise<BatchDeleteChunkResult> => {
      const personalIds: string[] = []
      const gatewayIds: string[] = []
      for (const id of chunk) {
        const item = entriesByIdRef.current.get(id)
        if (item?.scope === 'personal') {
          personalIds.push(id)
        } else if (item) {
          gatewayIds.push(id)
        }
      }

      const results: BatchDeleteChunkResult[] = []
      if (personalIds.length > 0) {
        results.push(await runChunkedBatchDelete(personalIds, gatewayApi.batchDeleteMyModels))
      }
      if (gatewayIds.length > 0) {
        const idsByTeam = groupModelIdsByTeamId(gatewayIds, resolveTeamIdForModel)
        results.push(
          await runChunkedBatchDeleteByTeamIds(idsByTeam, (teamId, teamChunk) =>
            gatewayApi.batchDeleteModels(teamId, teamChunk)
          )
        )
      }
      return mergeDeleteResults(...results)
    },
    [resolveTeamIdForModel]
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
      const personalIds: string[] = []
      const gatewayIds: string[] = []
      for (const id of chunk) {
        const item = entriesByIdRef.current.get(id)
        if (item?.scope === 'personal') {
          personalIds.push(id)
        } else if (item) {
          gatewayIds.push(id)
        }
      }

      const results: BatchResyncChunkResult[] = []
      if (personalIds.length > 0) {
        results.push(await gatewayApi.batchResyncMyModels(personalIds))
      }
      if (gatewayIds.length > 0) {
        const idsByTeam = groupModelIdsByTeamId(gatewayIds, resolveTeamIdForModel)
        results.push(
          await runChunkedBatchResyncByTeamIds(idsByTeam, (teamId, teamChunk) =>
            gatewayApi.batchResyncCapabilities(teamId, teamChunk)
          )
        )
      }
      return mergeResyncResults(...results)
    },
    [resolveTeamIdForModel]
  )

  const { batchResyncing, runBatchResync } = useChunkedModelBatchResync({
    resyncChunk,
    onComplete: handleBatchResyncComplete,
  })

  const onBatchItemComplete = useCallback(
    (modelId: string, result: Parameters<typeof connectivityFieldsFromTestResult>[0]) => {
      const item = entriesByIdRef.current.get(modelId)
      if (!item) return
      const fields = connectivityFieldsFromTestResult(result)
      const cacheScope = item.scope === 'personal' ? 'personal' : 'team'
      patchModelConnectivityInCache(queryClient, modelId, fields, cacheScope)
    },
    [queryClient]
  )

  const testById = useCallback(
    async (id: string) => {
      const item = entriesByIdRef.current.get(id)
      if (!item) {
        return Promise.reject(new Error(`未知模型 ${id}`))
      }
      if (item.scope === 'personal') {
        return gatewayApi.testMyModel(id)
      }
      const teamId = resolveTeamIdForModel(id)
      if (!teamId) {
        return Promise.reject(new Error(`无法解析模型 ${id} 的团队归属`))
      }
      return gatewayApi.testModel(teamId, id)
    },
    [resolveTeamIdForModel]
  )

  const handleBatchTestComplete = useCallback(
    (failed: readonly string[]) => {
      invalidateUnifiedModelsCache(queryClient)
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
    [queryClient, toast]
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

  const connectivityModels = useMemo(
    () => filteredEntries.map(entryAsConnectivityModel),
    [filteredEntries]
  )

  const filterTestableForBatch = useCallback((entries: readonly GatewayModelListItem[]) => {
    if (!canShowBatchOpsRef.current) return []
    const ctx = permissionCtxRef.current
    const models = entries.map(entryAsConnectivityModel)
    return filterTestableConnectivityModels(models).filter((model) => {
      const item = entriesByIdRef.current.get(model.id)
      return item ? canManageUnifiedModelItem(item, ctx) : false
    })
  }, [])

  const filterResyncableForBatch = useCallback((entries: readonly GatewayModelListItem[]) => {
    const ctx = permissionCtxRef.current
    return entries.filter((item) => canResyncUnifiedModelItem(item, ctx))
  }, [])

  const handleTestAll = useCallback((): void => {
    populateTeamByModelId(filteredEntries)
    const testable = filterTestableForBatch(filteredEntries)
    if (testable.length === 0) return
    startBatchTest(testable)
  }, [filteredEntries, filterTestableForBatch, populateTeamByModelId, startBatchTest])

  const handleTestUntested = useCallback((): void => {
    populateTeamByModelId(filteredEntries)
    const untested = filterUntestedConnectivityModels(connectivityModels)
    const untestedIds = new Set(untested.map((m) => m.id))
    const entries = filteredEntries.filter((item) => untestedIds.has(item.id))
    const testable = filterTestableForBatch(entries)
    if (testable.length === 0) return
    startBatchTest(testable)
  }, [
    filteredEntries,
    connectivityModels,
    filterTestableForBatch,
    populateTeamByModelId,
    startBatchTest,
  ])

  const handleTestSelected = useCallback(
    (entries: readonly GatewayModelListItem[]): void => {
      populateTeamByModelId(entries)
      const testable = filterTestableForBatch(entries)
      if (testable.length === 0) return
      startBatchTest(testable)
    },
    [filterTestableForBatch, populateTeamByModelId, startBatchTest]
  )

  const handleResyncAll = useCallback((): void => {
    const resyncable = filterResyncableForBatch(filteredEntries)
    if (resyncable.length === 0) return
    populateTeamByModelId(resyncable)
    runBatchResync(resyncable.map((item) => item.id))
  }, [filteredEntries, filterResyncableForBatch, populateTeamByModelId, runBatchResync])

  const handleResyncSelected = useCallback(
    (entries: readonly GatewayModelListItem[]): void => {
      const resyncable = filterResyncableForBatch(entries)
      if (resyncable.length === 0) return
      populateTeamByModelId(resyncable)
      runBatchResync(resyncable.map((item) => item.id))
    },
    [filterResyncableForBatch, populateTeamByModelId, runBatchResync]
  )

  const failedDeletableCount = connectivitySummary.failed

  const deleteFailedLabel = useMemo((): string => {
    const labels = filteredEntries
      .filter(
        (item) => item.lastTestStatus === 'failed' && canDeleteUnifiedModelItem(item, permissionCtx)
      )
      .map((item) => item.title)
    return formatDeleteFailedConfirmLabel(failedDeletableCount, labels)
  }, [failedDeletableCount, filteredEntries, permissionCtx])

  const handleDeleteFailed = useCallback((): void => {
    if (failedDeletableCount === 0) return
    setDeleteFailedOpen(true)
  }, [failedDeletableCount])

  const handleConfirmDeleteFailed = useCallback((): void => {
    const ctx = permissionCtxRef.current
    const deletable = filteredEntries.filter(
      (item) => item.lastTestStatus === 'failed' && canDeleteUnifiedModelItem(item, ctx)
    )
    if (deletable.length === 0) return
    populateTeamByModelId(deletable)
    runBatchDelete(deletable.map((item) => item.id))
  }, [filteredEntries, populateTeamByModelId, runBatchDelete])

  const testableItems = useMemo(
    () => filterTestableConnectivityModels(connectivityModels),
    [connectivityModels]
  )

  const untestedTestableItems = useMemo(
    () => filterUntestedConnectivityModels(connectivityModels),
    [connectivityModels]
  )

  const batchTesting = batchTestState.running
  const batchBusy = batchTesting || batchResyncing || batchDeleting

  const formatBatchDeleteLabel = useCallback((entries: readonly GatewayModelListItem[]): string => {
    const labels = entries.map((item) => item.title)
    return formatBatchDeleteConfirmLabel(labels)
  }, [])

  const canBatchSelect = useCallback(
    (item: GatewayModelListItem) => canBatchSelectUnifiedModelItem(item, permissionCtxRef.current),
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
    canBatchSelect,
    connectivityModels,
  }
}
