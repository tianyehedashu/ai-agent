import { useCallback, useRef, useState } from 'react'

import { runChunkedBatchDelete, type BatchDeleteChunkResult } from '@/features/gateway-models/utils'
import { useToast } from '@/hooks/use-toast'

interface UseChunkedModelBatchDeleteOptions {
  deleteChunk: (chunk: string[]) => Promise<BatchDeleteChunkResult>
  onComplete?: (result: BatchDeleteChunkResult) => void
}

/** 分批 batch-delete：统一 loading 与 toast，供个人/团队模型列表复用 */
export function useChunkedModelBatchDelete({
  deleteChunk,
  onComplete,
}: UseChunkedModelBatchDeleteOptions): {
  batchDeleting: boolean
  runBatchDelete: (ids: readonly string[]) => void
} {
  const { toast } = useToast()
  const [batchDeleting, setBatchDeleting] = useState(false)
  const deleteChunkRef = useRef(deleteChunk)
  const onCompleteRef = useRef(onComplete)
  deleteChunkRef.current = deleteChunk
  onCompleteRef.current = onComplete

  const runBatchDelete = useCallback(
    (ids: readonly string[]): void => {
      if (ids.length === 0) return
      setBatchDeleting(true)
      void runChunkedBatchDelete(ids, (chunk) => deleteChunkRef.current(chunk))
        .then((result) => {
          const succeeded = result.succeeded.length
          const failed = result.failed.length
          if (failed > 0) {
            toast({
              title: '批量删除完成',
              description: `成功 ${String(succeeded)} 个，失败 ${String(failed)} 个`,
              variant: succeeded > 0 ? 'default' : 'destructive',
            })
          }
          onCompleteRef.current?.(result)
        })
        .catch((e: unknown) => {
          const msg = e instanceof Error ? e.message : String(e)
          toast({ title: '批量删除失败', description: msg, variant: 'destructive' })
        })
        .finally(() => {
          setBatchDeleting(false)
        })
    },
    [toast]
  )

  return { batchDeleting, runBatchDelete }
}
