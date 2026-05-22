import { startTransition, useCallback, useRef, useState } from 'react'

import { BATCH_TEST_CONCURRENCY } from '@/features/gateway-models/constants'
import { runWithConcurrency } from '@/features/gateway-models/utils'

export interface ConnectivityBatchTestState {
  running: boolean
  total: number
  done: number
  failedIds: string[]
  cancel: () => void
}

interface TestResultLike {
  success?: boolean
}

interface UseConnectivityBatchTestOptions {
  testById: (id: string) => Promise<TestResultLike>
  invalidate: () => void
  onComplete?: (failedIds: string[]) => void
}

interface UseConnectivityBatchTestReturn {
  state: ConnectivityBatchTestState
  start: (ids: readonly string[]) => void
  retestFailed: () => void
}

export function useConnectivityBatchTest(
  options: UseConnectivityBatchTestOptions
): UseConnectivityBatchTestReturn {
  const optionsRef = useRef(options)
  optionsRef.current = options

  const abortRef = useRef<AbortController | null>(null)
  const failedIdsRef = useRef<string[]>([])

  const [running, setRunning] = useState(false)
  const [total, setTotal] = useState(0)
  const [done, setDone] = useState(0)
  const [failedIds, setFailedIds] = useState<string[]>([])

  const cancel = useCallback((): void => {
    abortRef.current?.abort()
    abortRef.current = null
    setRunning(false)
  }, [])

  const publishProgress = useCallback((completed: number, failed: string[]): void => {
    startTransition(() => {
      setDone(completed)
      const snapshot = [...failed]
      failedIdsRef.current = snapshot
      setFailedIds(snapshot)
    })
  }, [])

  const runTests = useCallback(
    async (ids: readonly string[]): Promise<void> => {
      const unique = [...new Set(ids)]
      if (unique.length === 0) return

      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setRunning(true)
      setTotal(unique.length)
      setDone(0)
      failedIdsRef.current = []
      setFailedIds([])

      const failed: string[] = []
      let completed = 0

      try {
        await runWithConcurrency(
          unique,
          BATCH_TEST_CONCURRENCY,
          async (id) => {
            if (controller.signal.aborted) return
            try {
              const result = await optionsRef.current.testById(id)
              if (!result.success) failed.push(id)
            } catch {
              failed.push(id)
            }
            completed += 1
            publishProgress(completed, failed)
          },
          controller.signal
        )
        if (!controller.signal.aborted) {
          optionsRef.current.invalidate()
          optionsRef.current.onComplete?.(failed)
        }
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null
        }
        if (!controller.signal.aborted) {
          publishProgress(completed, failed)
        }
        setRunning(false)
      }
    },
    [publishProgress]
  )

  const start = useCallback(
    (ids: readonly string[]): void => {
      void runTests(ids)
    },
    [runTests]
  )

  const retestFailed = useCallback((): void => {
    const ids = failedIdsRef.current
    if (ids.length === 0) return
    void runTests(ids)
  }, [runTests])

  return {
    state: {
      running,
      total,
      done,
      failedIds,
      cancel,
    },
    start,
    retestFailed,
  }
}
