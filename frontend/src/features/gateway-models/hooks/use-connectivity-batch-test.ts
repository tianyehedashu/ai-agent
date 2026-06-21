import { startTransition, useCallback, useRef, useState } from 'react'

import type { GatewayModelTestResult } from '@/api/gateway/models'
import {
  batchConnectivityIncludesVideoGeneration,
  filterTestableConnectivityModels,
  runBatchConnectivityTests,
  type ModelWithConnectivityStatus,
} from '@/features/gateway-models/utils'

export interface ConnectivityBatchTestState {
  running: boolean
  total: number
  done: number
  failedIds: string[]
  includesVideoProbe: boolean
  cancel: () => void
}

interface UseConnectivityBatchTestOptions {
  testById: (id: string) => Promise<GatewayModelTestResult>
  invalidate: () => void
  onItemComplete?: (modelId: string, result: GatewayModelTestResult) => void
  onComplete?: (failedIds: string[]) => void
}

interface UseConnectivityBatchTestReturn {
  state: ConnectivityBatchTestState
  start: (items: readonly ModelWithConnectivityStatus[]) => void
  retestFailed: () => void
}

export function useConnectivityBatchTest(
  options: UseConnectivityBatchTestOptions
): UseConnectivityBatchTestReturn {
  const optionsRef = useRef(options)
  optionsRef.current = options

  const abortRef = useRef<AbortController | null>(null)
  const failedIdsRef = useRef<string[]>([])
  const lastRunItemsRef = useRef<ModelWithConnectivityStatus[]>([])
  const isRunningRef = useRef(false)

  const [running, setRunning] = useState(false)
  const [total, setTotal] = useState(0)
  const [done, setDone] = useState(0)
  const [failedIds, setFailedIds] = useState<string[]>([])
  const [includesVideoProbe, setIncludesVideoProbe] = useState(false)

  const cancel = useCallback((): void => {
    abortRef.current?.abort()
    abortRef.current = null
    setRunning(false)
  }, [])

  const publishProgress = useCallback((completed: number, failed: readonly string[]): void => {
    startTransition(() => {
      setDone(completed)
      const snapshot = [...failed]
      failedIdsRef.current = snapshot
      setFailedIds(snapshot)
    })
  }, [])

  const runTests = useCallback(
    async (items: readonly ModelWithConnectivityStatus[]): Promise<void> => {
      if (isRunningRef.current) return
      const testable = filterTestableConnectivityModels(items)
      if (testable.length === 0) return

      isRunningRef.current = true
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      lastRunItemsRef.current = testable
      const hasVideoProbe = batchConnectivityIncludesVideoGeneration(testable)

      setRunning(true)
      setTotal(testable.length)
      setDone(0)
      setIncludesVideoProbe(hasVideoProbe)
      failedIdsRef.current = []
      setFailedIds([])

      try {
        const failed = await runBatchConnectivityTests(
          testable,
          (id) => optionsRef.current.testById(id),
          {
            signal: controller.signal,
            onProgress: (completed, _total, failedSnapshot) => {
              publishProgress(completed, failedSnapshot)
            },
            onItemComplete: (modelId, result) => {
              optionsRef.current.onItemComplete?.(modelId, result)
            },
          }
        )
        if (!controller.signal.aborted) {
          publishProgress(testable.length, failed)
          optionsRef.current.invalidate()
          optionsRef.current.onComplete?.(failed)
        }
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null
        }
        isRunningRef.current = false
        setRunning(false)
      }
    },
    [publishProgress]
  )

  const start = useCallback(
    (items: readonly ModelWithConnectivityStatus[]): void => {
      if (isRunningRef.current) return
      void runTests(items)
    },
    [runTests]
  )

  const retestFailed = useCallback((): void => {
    if (isRunningRef.current) return
    const failedSet = new Set(failedIdsRef.current)
    const items = lastRunItemsRef.current.filter((m) => failedSet.has(m.id))
    if (items.length === 0) return
    void runTests(items)
  }, [runTests])

  return {
    state: {
      running,
      total,
      done,
      failedIds,
      includesVideoProbe,
      cancel,
    },
    start,
    retestFailed,
  }
}
