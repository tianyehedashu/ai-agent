/**
 * 调用指南「试调虚拟 Key」选择 hook
 *
 * - 不在进入页面时自动创建 vkey；不再持久化明文
 * - 列表数据来自服务端 `listKeys`（支持多团队聚合）
 * - 上次选中 id 经 `usePlaygroundVkeySelectionStore` 持久化
 * - 切换时按需 `revealKey`，明文仅在内存
 */

import { useCallback, useEffect, useMemo, useRef } from 'react'

import { useQueries } from '@tanstack/react-query'

import { gatewayApi, type VirtualKey } from '@/api/gateway'
import { usePlaygroundVkeySelectionStore } from '@/stores/playground-vkey-selection'

import { migrateLegacyPlaygroundVkeyStorage } from './playground-vkey-persist'

export interface PlaygroundVkeyBootstrap {
  /** 创建 Key 后导航带入的明文（仅当与 keyId 同时存在且匹配选中 id 时生效） */
  plain?: string | null
  keyId?: string | null
  /** URL `?key_id=` 或导航 state；仅在 listKeys 结果包含该 id 时写入选中（避免跨团队无效 id） */
  preferKeyId?: string | null
}

export interface UsePlaygroundVirtualKeyOptions {
  bootstrap?: PlaygroundVkeyBootstrap
  /** 单团队上下文（兼容旧调用） */
  teamId?: string | null
  /** 多团队聚合 Key 列表（Guide：未选凭据时跨 membership） */
  teamIds?: readonly string[] | null
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
  isRefreshingKeys: boolean
  refreshKeys: () => void
}

function isVirtualKeyOptions(
  input: PlaygroundVkeyBootstrap | UsePlaygroundVirtualKeyOptions
): input is UsePlaygroundVirtualKeyOptions {
  return 'teamId' in input || 'teamIds' in input || 'bootstrap' in input
}

function normalizeVirtualKeyOptions(
  input?: PlaygroundVkeyBootstrap | UsePlaygroundVirtualKeyOptions
): UsePlaygroundVirtualKeyOptions {
  if (input === undefined) return {}
  if (isVirtualKeyOptions(input)) return input
  return { bootstrap: input }
}

function resolveTeamIds(options: UsePlaygroundVirtualKeyOptions): string[] {
  if (options.teamIds && options.teamIds.length > 0) return [...options.teamIds]
  if (options.teamId) return [options.teamId]
  return []
}

function mergeVisibleKeys(results: readonly (VirtualKey[] | undefined)[]): VirtualKey[] {
  const byId = new Map<string, VirtualKey>()
  for (const rows of results) {
    for (const key of rows ?? []) {
      if (key.is_system || !key.is_active) continue
      byId.set(key.id, key)
    }
  }
  return Array.from(byId.values())
}

export function usePlaygroundVirtualKey(
  bootstrapOrOptions?: PlaygroundVkeyBootstrap | UsePlaygroundVirtualKeyOptions
): UsePlaygroundVirtualKeyReturn {
  const options = normalizeVirtualKeyOptions(bootstrapOrOptions)
  const bootstrap = options.bootstrap
  const { teamId, teamIds: teamIdsOption } = options
  const teamIds = useMemo(
    () => resolveTeamIds({ teamId, teamIds: teamIdsOption }),
    [teamId, teamIdsOption]
  )

  const selectedKeyId = usePlaygroundVkeySelectionStore((s) => s.lastSelectedId)
  const setLastSelectedId = usePlaygroundVkeySelectionStore((s) => s.setLastSelectedId)
  const explicitlyClearedRef = useRef(false)
  const prevTeamScopeRef = useRef<string | undefined>(undefined)

  const teamScopeKey = teamIds.join('|')

  useEffect(() => {
    if (prevTeamScopeRef.current === undefined) {
      prevTeamScopeRef.current = teamScopeKey
      return
    }
    if (prevTeamScopeRef.current === teamScopeKey) return
    prevTeamScopeRef.current = teamScopeKey
    explicitlyClearedRef.current = false
    setLastSelectedId(null)
  }, [teamScopeKey, setLastSelectedId])

  useEffect(() => {
    const migratedId = migrateLegacyPlaygroundVkeyStorage()
    if (migratedId !== null && selectedKeyId === null && !explicitlyClearedRef.current) {
      setLastSelectedId(migratedId)
    }
  }, [selectedKeyId, setLastSelectedId])

  const keysQueries = useQueries({
    queries: teamIds.map((id) => ({
      queryKey: ['gateway', 'keys', id, 'playground'] as const,
      queryFn: () => gatewayApi.listKeys(id),
      enabled: Boolean(id),
      staleTime: 30_000,
    })),
  })

  const visibleKeys = useMemo(() => mergeVisibleKeys(keysQueries.map((q) => q.data)), [keysQueries])

  const isLoadingKeys = teamIds.length > 0 && keysQueries.some((q) => q.isLoading)
  const isRefreshingKeys = keysQueries.some((q) => q.isFetching)

  useEffect(() => {
    if (isRefreshingKeys) return
    if (selectedKeyId && !visibleKeys.some((k) => k.id === selectedKeyId)) {
      const next = visibleKeys[0]?.id ?? null
      explicitlyClearedRef.current = false
      setLastSelectedId(next)
    }
  }, [isRefreshingKeys, selectedKeyId, visibleKeys, setLastSelectedId])

  useEffect(() => {
    if (selectedKeyId !== null) return
    if (explicitlyClearedRef.current) return
    if (visibleKeys.length === 0) return
    setLastSelectedId(visibleKeys[0].id)
  }, [selectedKeyId, visibleKeys, setLastSelectedId])

  const preferKeyId = bootstrap?.preferKeyId ?? null

  useEffect(() => {
    if (!preferKeyId || isRefreshingKeys) return
    if (!visibleKeys.some((k) => k.id === preferKeyId)) return
    if (selectedKeyId === preferKeyId) return
    explicitlyClearedRef.current = false
    setLastSelectedId(preferKeyId)
  }, [preferKeyId, isRefreshingKeys, visibleKeys, selectedKeyId, setLastSelectedId])

  const selectedKey = useMemo<VirtualKey | null>(
    () => visibleKeys.find((k) => k.id === selectedKeyId) ?? null,
    [visibleKeys, selectedKeyId]
  )

  const revealTeamId = selectedKey?.team_id ?? teamIds[0]

  const bootstrapPlain = bootstrap?.plain?.trim() ?? null
  const bootstrapKeyId = bootstrap?.keyId ?? null
  const bootstrapActive =
    bootstrapPlain !== null &&
    bootstrapKeyId !== null &&
    selectedKeyId !== null &&
    bootstrapKeyId === selectedKeyId

  const revealQuery = useQueries({
    queries: [
      {
        queryKey: ['gateway', 'keys', revealTeamId, selectedKeyId, 'reveal'] as const,
        queryFn: () => {
          if (selectedKeyId === null || selectedKey === null) {
            return Promise.reject(new Error('未选择虚拟 Key'))
          }
          return gatewayApi.revealKey(selectedKey.team_id, selectedKeyId)
        },
        enabled: selectedKeyId !== null && selectedKey !== null && !bootstrapActive,
        staleTime: 5 * 60_000,
        retry: false,
      },
    ],
  })[0]

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

  const refreshKeys = useCallback((): void => {
    for (const query of keysQueries) {
      void query.refetch()
    }
  }, [keysQueries])

  return {
    keys: visibleKeys,
    isLoadingKeys,
    selectedKey,
    selectedKeyId,
    selectKey,
    plain,
    isRevealing: revealQuery.isFetching && selectedKeyId !== null,
    revealError,
    isRefreshingKeys,
    refreshKeys,
  }
}
