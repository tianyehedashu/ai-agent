/**
 * 调用指南「试调专用 Key」缓存（多把）
 *
 * - 首次进入：若本地没有可复用 Key，自动创建一把（明文只在 createKey 响应里出现一次，丢失不可恢复）
 * - 缓存结构 v2：保留多把已创建的 Key，便于在多模型 / 多场景切换
 * - 自动迁移 v1 单把缓存
 * - 缓存随 listKeys 校验：服务端已撤销的会自动从缓存清除
 *
 * 安全性：
 * - 缓存遵循 client-localstorage-schema：版本字段 v: 2，仅最小字段
 * - 命名带 "调用指南自动 Key" 前缀，便于在虚拟 Key 页识别 / 撤销
 * - 不写入登录态以外的设备同步存储
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { useQuery, useQueryClient } from '@tanstack/react-query'

import { gatewayApi, type VirtualKey } from '@/api/gateway'

const STORAGE_KEY_V2 = 'gateway:playground:vkey:v2'
const STORAGE_KEY_V1 = 'gateway:playground:vkey:v1'
const KEY_NAME_PREFIX = '调用指南自动 Key'

export interface CachedPlaygroundKey {
  id: string
  plain: string
  name: string
  createdAt: string
  lastUsedAt: string
}

interface CacheV2 {
  v: 2
  items: CachedPlaygroundKey[]
  lastSelectedId: string | null
}

const EMPTY_CACHE: CacheV2 = { v: 2, items: [], lastSelectedId: null }

function isItem(value: unknown): value is CachedPlaygroundKey {
  if (typeof value !== 'object' || value === null) return false
  const v = value as Record<string, unknown>
  return typeof v.id === 'string' && typeof v.plain === 'string' && typeof v.name === 'string'
}

function readCache(): CacheV2 {
  if (typeof window === 'undefined') return EMPTY_CACHE
  try {
    const v2Raw = window.localStorage.getItem(STORAGE_KEY_V2)
    if (v2Raw) {
      const parsed = JSON.parse(v2Raw) as Partial<CacheV2>
      if (parsed.v === 2 && Array.isArray(parsed.items)) {
        const items: CachedPlaygroundKey[] = parsed.items.filter(isItem).map((it) => ({
          id: it.id,
          plain: it.plain,
          name: it.name,
          createdAt: typeof it.createdAt === 'string' ? it.createdAt : '',
          lastUsedAt: typeof it.lastUsedAt === 'string' ? it.lastUsedAt : '',
        }))
        return { v: 2, items, lastSelectedId: parsed.lastSelectedId ?? null }
      }
    }
    const v1Raw = window.localStorage.getItem(STORAGE_KEY_V1)
    if (v1Raw) {
      const parsed = JSON.parse(v1Raw) as {
        v?: number
        id?: string
        plain?: string
        name?: string
        createdAt?: string
      }
      if (parsed.v === 1 && parsed.id && parsed.plain && parsed.name) {
        const item: CachedPlaygroundKey = {
          id: parsed.id,
          plain: parsed.plain,
          name: parsed.name,
          createdAt: parsed.createdAt ?? '',
          lastUsedAt: new Date().toISOString(),
        }
        const migrated: CacheV2 = { v: 2, items: [item], lastSelectedId: item.id }
        writeCache(migrated)
        try {
          window.localStorage.removeItem(STORAGE_KEY_V1)
        } catch {
          // 隐私模式下忽略
        }
        return migrated
      }
    }
  } catch {
    // 解析失败：返回空缓存
  }
  return EMPTY_CACHE
}

function writeCache(value: CacheV2): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(STORAGE_KEY_V2, JSON.stringify(value))
  } catch {
    // 无痕模式 / 配额拒写时静默放弃
  }
}

function buildKeyName(): string {
  return `${KEY_NAME_PREFIX} ${new Date().toLocaleString()}`
}

function resolveSelected(cache: CacheV2): CachedPlaygroundKey | null {
  if (cache.items.length === 0) return null
  const fromCache = cache.items.find((i) => i.id === cache.lastSelectedId)
  return fromCache ?? cache.items[0]
}

export interface UsePlaygroundVirtualKeyOptions {
  /** 是否允许在缓存为空时自动创建一把（一次性） */
  autoEnsure: boolean
}

export interface UsePlaygroundVirtualKeyReturn {
  items: CachedPlaygroundKey[]
  selected: CachedPlaygroundKey | null
  ensuring: boolean
  error: Error | null
  selectKey: (id: string) => void
  regenerate: () => Promise<CachedPlaygroundKey>
  /** 不传 id 清空全部本地缓存；传 id 仅清单条 */
  forget: (id?: string) => void
}

export function usePlaygroundVirtualKey(
  options: UsePlaygroundVirtualKeyOptions
): UsePlaygroundVirtualKeyReturn {
  const { autoEnsure } = options
  const [cache, setCache] = useState<CacheV2>(readCache)
  const [ensuring, setEnsuring] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const ensureAttemptedRef = useRef(false)
  const queryClient = useQueryClient()

  const keysQuery = useQuery({
    queryKey: ['gateway', 'keys'],
    queryFn: () => gatewayApi.listKeys(),
    staleTime: 30_000,
  })

  const applyCache = useCallback((updater: (prev: CacheV2) => CacheV2) => {
    setCache((prev) => {
      const next = updater(prev)
      writeCache(next)
      return next
    })
  }, [])

  const createAndAdd = useCallback(async (): Promise<CachedPlaygroundKey> => {
    const created = await gatewayApi.createKey({
      name: buildKeyName(),
      store_full_messages: false,
      guardrail_enabled: true,
    })
    const item: CachedPlaygroundKey = {
      id: created.id,
      plain: created.plain_key,
      name: created.name,
      createdAt: created.created_at,
      lastUsedAt: new Date().toISOString(),
    }
    // 立即把新 vkey 注入 React Query 缓存，避免在 refetch 完成前
    // 校验 effect 把刚加入 cache 的 item 误判为「服务端已撤销」而清掉。
    queryClient.setQueryData<VirtualKey[] | undefined>(['gateway', 'keys'], (prev) => {
      if (!prev) return [created]
      if (prev.some((k) => k.id === created.id)) return prev
      return [created, ...prev]
    })
    applyCache((prev) => ({
      v: 2,
      items: [item, ...prev.items.filter((i) => i.id !== item.id)],
      lastSelectedId: item.id,
    }))
    void queryClient.invalidateQueries({ queryKey: ['gateway', 'keys'] })
    return item
  }, [applyCache, queryClient])

  useEffect(() => {
    if (keysQuery.isFetching) return
    const keys = keysQuery.data
    if (!keys) return
    const activeIds = new Set(keys.filter((k) => k.is_active).map((k) => k.id))
    // 用 setCache updater 拿最新 cache，避免在 cache 变化时被重复触发；
    // 同时确保 createAndAdd 后还没等到 refetch 时不会误清新加入的 item
    setCache((prev) => {
      if (prev.items.length === 0) return prev
      const filtered = prev.items.filter((i) => activeIds.has(i.id))
      if (filtered.length === prev.items.length) return prev
      const nextSelectedId: string | null =
        filtered.length === 0
          ? null
          : (filtered.find((i) => i.id === prev.lastSelectedId)?.id ?? filtered[0].id)
      const next: CacheV2 = { v: 2, items: filtered, lastSelectedId: nextSelectedId }
      writeCache(next)
      return next
    })
  }, [keysQuery.isFetching, keysQuery.data])

  // 当本地缓存被清空（手动 forget 或服务端撤销）后，允许 autoEnsure 再次创建
  useEffect(() => {
    if (cache.items.length === 0) ensureAttemptedRef.current = false
  }, [cache.items.length])

  useEffect(() => {
    if (!autoEnsure) return
    if (cache.items.length > 0) return
    if (keysQuery.isFetching) return
    if (!keysQuery.data) return
    if (ensureAttemptedRef.current) return
    ensureAttemptedRef.current = true
    setEnsuring(true)
    setError(null)
    createAndAdd()
      .catch((e: unknown) => {
        setError(e instanceof Error ? e : new Error('自动创建虚拟 Key 失败'))
      })
      .finally(() => {
        setEnsuring(false)
      })
  }, [autoEnsure, cache.items.length, keysQuery.isFetching, keysQuery.data, createAndAdd])

  const selectKey = useCallback(
    (id: string) => {
      applyCache((prev) => {
        if (!prev.items.some((i) => i.id === id)) return prev
        return { v: 2, items: prev.items, lastSelectedId: id }
      })
    },
    [applyCache]
  )

  const regenerate = useCallback(async (): Promise<CachedPlaygroundKey> => {
    setEnsuring(true)
    setError(null)
    try {
      return await createAndAdd()
    } catch (e: unknown) {
      const err = e instanceof Error ? e : new Error('创建虚拟 Key 失败')
      setError(err)
      throw err
    } finally {
      setEnsuring(false)
    }
  }, [createAndAdd])

  const forget = useCallback(
    (id?: string) => {
      if (id === undefined) {
        applyCache(() => EMPTY_CACHE)
        ensureAttemptedRef.current = false
        return
      }
      applyCache((prev) => {
        const items = prev.items.filter((i) => i.id !== id)
        const lastSelectedId: string | null =
          items.length === 0
            ? null
            : (items.find((i) => i.id === prev.lastSelectedId)?.id ?? items[0].id)
        return { v: 2, items, lastSelectedId }
      })
    },
    [applyCache]
  )

  const selected = resolveSelected(cache)

  return {
    items: cache.items,
    selected,
    ensuring,
    error,
    selectKey,
    regenerate,
    forget,
  }
}
