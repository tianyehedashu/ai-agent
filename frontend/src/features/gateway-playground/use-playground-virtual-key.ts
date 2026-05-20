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
import { useGatewayTeamStore } from '@/stores/gateway-team'
import { usePlaygroundVkeySelectionStore } from '@/stores/playground-vkey-selection'

import { migrateLegacyPlaygroundVkeyStorage } from './playground-vkey-persist'

export interface PlaygroundVkeyBootstrap {
  /** 创建 Key 后导航带入的明文（仅当与 keyId 同时存在且匹配选中 id 时生效） */
  plain?: string | null
  keyId?: string | null
  /** URL `?key_id=` 或导航 state；仅在 listKeys 结果包含该 id 时写入选中（避免跨团队无效 id） */
  preferKeyId?: string | null
}

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

export function usePlaygroundVirtualKey(
  bootstrap?: PlaygroundVkeyBootstrap
): UsePlaygroundVirtualKeyReturn {
  const selectedKeyId = usePlaygroundVkeySelectionStore((s) => s.lastSelectedId)
  const setLastSelectedId = usePlaygroundVkeySelectionStore((s) => s.setLastSelectedId)
  const currentTeamId = useGatewayTeamStore((s) => s.currentTeamId)
  const explicitlyClearedRef = useRef(false)
  const prevTeamIdRef = useRef<string | null | undefined>(undefined)

  useEffect(() => {
    if (prevTeamIdRef.current === undefined) {
      prevTeamIdRef.current = currentTeamId
      return
    }
    if (prevTeamIdRef.current === currentTeamId) return
    prevTeamIdRef.current = currentTeamId
    explicitlyClearedRef.current = false
    setLastSelectedId(null)
  }, [currentTeamId, setLastSelectedId])

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

  const preferKeyId = bootstrap?.preferKeyId ?? null

  useEffect(() => {
    if (!preferKeyId || keysQuery.isFetching || !keysQuery.data) return
    if (!visibleKeys.some((k) => k.id === preferKeyId)) return
    if (selectedKeyId === preferKeyId) return
    explicitlyClearedRef.current = false
    setLastSelectedId(preferKeyId)
  }, [
    preferKeyId,
    keysQuery.isFetching,
    keysQuery.data,
    visibleKeys,
    selectedKeyId,
    setLastSelectedId,
  ])

  const selectedKey = useMemo<VirtualKey | null>(
    () => visibleKeys.find((k) => k.id === selectedKeyId) ?? null,
    [visibleKeys, selectedKeyId]
  )

  const bootstrapPlain = bootstrap?.plain?.trim() ?? null
  const bootstrapKeyId = bootstrap?.keyId ?? null
  const bootstrapActive =
    bootstrapPlain !== null &&
    bootstrapKeyId !== null &&
    selectedKeyId !== null &&
    bootstrapKeyId === selectedKeyId

  const revealQuery = useQuery({
    queryKey: ['gateway', 'keys', selectedKeyId, 'reveal'] as const,
    queryFn: () => {
      if (selectedKeyId === null) {
        return Promise.reject(new Error('未选择虚拟 Key'))
      }
      return gatewayApi.revealKey(selectedKeyId)
    },
    enabled: selectedKeyId !== null && selectedKey !== null && !bootstrapActive,
    staleTime: 5 * 60_000,
    retry: false,
  })

  const plain = bootstrapActive ? bootstrapPlain : (revealQuery.data?.plain_key ?? null)
  const revealError =
    bootstrapActive || revealQuery.error === null
      ? null
      : revealQuery.error instanceof Error
        ? revealQuery.error
        : null

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
