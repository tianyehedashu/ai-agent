/**
 * 复制到剪贴板，并在一段时间内标记「已复制」状态
 */

import { useState, useCallback } from 'react'

const COPIED_RESET_MS = 1500

/** 单次复制，返回 [copy, copied] */
export function useCopyToClipboard(): [(text: string) => Promise<void>, boolean] {
  const [copied, setCopied] = useState(false)
  const copy = useCallback(async (text: string) => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => {
      setCopied(false)
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
  const copy = useCallback(async (text: string, key: K) => {
    await navigator.clipboard.writeText(text)
    setCopiedKey(key)
    setTimeout(() => {
      setCopiedKey(null)
    }, COPIED_RESET_MS)
  }, [])
  return [copy, copiedKey]
}
