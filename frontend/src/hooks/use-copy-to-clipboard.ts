/**
 * 复制到剪贴板，并在一段时间内标记「已复制」状态
 */

import { useState, useCallback, useEffect, useRef } from 'react'

import { copyToClipboard } from '@/lib/utils'

const COPIED_RESET_MS = 1500

/** 单次复制，返回 [copy, copied] */
export function useCopyToClipboard(): [(text: string) => Promise<void>, boolean] {
  const [copied, setCopied] = useState(false)
  const resetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (resetTimerRef.current !== null) {
        clearTimeout(resetTimerRef.current)
      }
    }
  }, [])

  const copy = useCallback(async (text: string) => {
    await copyToClipboard(text)
    if (resetTimerRef.current !== null) {
      clearTimeout(resetTimerRef.current)
    }
    setCopied(true)
    resetTimerRef.current = setTimeout(() => {
      setCopied(false)
      resetTimerRef.current = null
    }, COPIED_RESET_MS)
  }, [])
  return [copy, copied]
}

/** 多行/多键复制，返回 [copy(text, key), copiedKey] */
export function useCopyToClipboardKeyed<K = number>(): [
  (text: string, key: K) => Promise<void>,
  K | null,
] {
  const [copiedKey, setCopiedKey] = useState<K | null>(null)
  const resetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (resetTimerRef.current !== null) {
        clearTimeout(resetTimerRef.current)
      }
    }
  }, [])

  const copy = useCallback(async (text: string, key: K) => {
    await copyToClipboard(text)
    if (resetTimerRef.current !== null) {
      clearTimeout(resetTimerRef.current)
    }
    setCopiedKey(key)
    resetTimerRef.current = setTimeout(() => {
      setCopiedKey(null)
      resetTimerRef.current = null
    }, COPIED_RESET_MS)
  }, [])
  return [copy, copiedKey]
}
