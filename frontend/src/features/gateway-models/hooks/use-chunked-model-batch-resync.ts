import { useCallback, useRef, useState } from 'react'

import { runChunkedBatchResync, type BatchResyncChunkResult } from '@/features/gateway-models/utils'
import { useToast } from '@/hooks/use-toast'

interface UseChunkedModelBatchResyncOptions {
  resyncChunk: (chunk: string[]) => Promise<BatchResyncChunkResult>
  onComplete?: (result: BatchResyncChunkResult) => void
}

/** 分批 batch-resync-capabilities：统一 loading 与 toast，供团队模型列表复用 */
export function useChunkedModelBatchResync({
  resyncChunk,
  onComplete,
}: UseChunkedModelBatchResyncOptions): {
  batchResyncing: boolean
  runBatchResync: (ids: readonly string[]) => void
} {
  const { toast } = useToast()
  const [batchResyncing, setBatchResyncing] = useState(false)
  const resyncChunkRef = useRef(resyncChunk)
  const onCompleteRef = useRef(onComplete)
  resyncChunkRef.current = resyncChunk
  onCompleteRef.current = onComplete

  const runBatchResync = useCallback(
    (ids: readonly string[]): void => {
      if (ids.length === 0) return
      setBatchResyncing(true)
      void runChunkedBatchResync(ids, (chunk) => resyncChunkRef.current(chunk))
        .then((result) => {
          const succeeded = result.succeeded.length
          const failed = result.failed.length
          if (failed > 0) {
            toast({
              title: '批量同步完成',
              description: `成功 ${String(succeeded)} 个，失败 ${String(failed)} 个`,
              variant: succeeded > 0 ? 'default' : 'destructive',
            })
          } else if (succeeded > 0) {
            toast({
              title: `已从目录同步 ${String(succeeded)} 个模型能力`,
            })
          }
          onCompleteRef.current?.(result)
        })
        .catch((e: unknown) => {
          const msg = e instanceof Error ? e.message : String(e)
          toast({ title: '批量同步失败', description: msg, variant: 'destructive' })
        })
        .finally(() => {
          setBatchResyncing(false)
        })
    },
    [toast]
  )

  return { batchResyncing, runBatchResync }
}
