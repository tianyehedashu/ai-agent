/**
 * 调用指南「试调虚拟 Key」选择 hook
 *
 * - 不在进入页面时自动创建 vkey；不再持久化明文
 * - 列表数据来自服务端 `listKeys`
 * - 上次选中 id 经 `usePlaygroundVkeySelectionStore` 持久化
 * - 切换时按需 `revealKey`，明文仅在内存
 */

import { useCallback, useEffect, useMemo, useRef } from 'react'

import { useQuery } from '@tanstack/react-query'

import { gatewayApi, type VirtualKey } from '@/api/gateway'
import { usePlaygroundVkeySelectionStore } from '@/stores/playground-vkey-selection'

import { migrateLegacyPlaygroundVkeyStorage } from './playground-vkey-persist'

export interface UsePlaygroundVirtualKeyReturn {
  keys: VirtualKey[]
  isLoadingKeys: boolean
  selectedKey: VirtualKey | null
  selectedKeyId: string | null
  selectKey: (id: string | null) => void
  plain: string | null
  isRevealing: boolean
  revealError: Error | null
}

export function usePlaygroundVirtualKey(): UsePlaygroundVirtualKeyReturn {
  const selectedKeyId = usePlaygroundVkeySelectionStore((s) => s.lastSelectedId)
  const setLastSelectedId = usePlaygroundVkeySelectionStore((s) => s.setLastSelectedId)
  const explicitlyClearedRef = useRef(false)

  useEffect(() => {
    const migratedId = migrateLegacyPlaygroundVkeyStorage()
    if (migratedId !== null && selectedKeyId === null && !explicitlyClearedRef.current) {
      setLastSelectedId(migratedId)
    }
  }, [selectedKeyId, setLastSelectedId])

  const keysQuery = useQuery({
    queryKey: ['gateway', 'keys'],
    queryFn: () => gatewayApi.listKeys(),
    staleTime: 30_000,
  })

  const visibleKeys = useMemo<VirtualKey[]>(
    () => (keysQuery.data ?? []).filter((k) => !k.is_system && k.is_active),
    [keysQuery.data]
  )

  useEffect(() => {
    if (keysQuery.isFetching || !keysQuery.data) return
    if (selectedKeyId && !visibleKeys.some((k) => k.id === selectedKeyId)) {
      const next = visibleKeys[0]?.id ?? null
      explicitlyClearedRef.current = false
      setLastSelectedId(next)
    }
  }, [keysQuery.isFetching, keysQuery.data, selectedKeyId, visibleKeys, setLastSelectedId])

  useEffect(() => {
    if (selectedKeyId !== null) return
    if (explicitlyClearedRef.current) return
    if (visibleKeys.length === 0) return
    setLastSelectedId(visibleKeys[0].id)
  }, [selectedKeyId, visibleKeys, setLastSelectedId])

  const selectedKey = useMemo<VirtualKey | null>(
    () => visibleKeys.find((k) => k.id === selectedKeyId) ?? null,
    [visibleKeys, selectedKeyId]
  )

  const revealQuery = useQuery({
    queryKey: ['gateway', 'keys', selectedKeyId, 'reveal'] as const,
    queryFn: () => {
      if (selectedKeyId === null) {
        return Promise.reject(new Error('未选择虚拟 Key'))
      }
      return gatewayApi.revealKey(selectedKeyId)
    },
    enabled: selectedKeyId !== null && selectedKey !== null,
    staleTime: 5 * 60_000,
    retry: false,
  })

  const plain = revealQuery.data?.plain_key ?? null
  const revealError = revealQuery.error instanceof Error ? revealQuery.error : null

  const selectKey = useCallback(
    (id: string | null): void => {
      explicitlyClearedRef.current = id === null
      setLastSelectedId(id)
    },
    [setLastSelectedId]
  )

  return {
    keys: visibleKeys,
    isLoadingKeys: keysQuery.isLoading,
    selectedKey,
    selectedKeyId,
    selectKey,
    plain,
    isRevealing: revealQuery.isFetching && selectedKeyId !== null,
    revealError,
  }
}
