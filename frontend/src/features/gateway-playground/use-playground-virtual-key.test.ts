/**
 * usePlaygroundVirtualKey 行为单测
 *
 * 重点覆盖：
 * - 旧 v1 单把缓存自动迁移到 v2 列表
 * - autoEnsure：缓存为空时自动调用 createKey 创建一把并写入缓存
 * - 校验：listKeys 中已不存在的 Key 会从缓存中清除
 * - selectKey / regenerate / forget 行为
 */

import React, { act } from 'react'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, test, vi } from 'vitest'

import type { VirtualKey, VirtualKeyCreated } from '@/api/gateway'

import { usePlaygroundVirtualKey } from './use-playground-virtual-key'

const createKeyMock = vi.fn(
  (_body: Record<string, unknown>): Promise<VirtualKeyCreated> =>
    Promise.reject(new Error('createKeyMock not configured'))
)
const listKeysMock = vi.fn((): Promise<VirtualKey[]> => Promise.resolve([]))

vi.mock('@/api/gateway', () => ({
  gatewayApi: {
    createKey: (body: Record<string, unknown>) => createKeyMock(body),
    listKeys: () => listKeysMock(),
  },
}))

const STORAGE_KEY_V1 = 'gateway:playground:vkey:v1'
const STORAGE_KEY_V2 = 'gateway:playground:vkey:v2'

interface PersistedV2 {
  v: number
  items: { id: string; plain: string }[]
  lastSelectedId: string | null
}

function readPersistedV2(): PersistedV2 {
  return JSON.parse(window.localStorage.getItem(STORAGE_KEY_V2) ?? '{}') as PersistedV2
}

function makeVKey(id: string, name = 'k', isActive = true): VirtualKey {
  return {
    id,
    team_id: 't',
    name,
    masked_key: `sk-gw-***${id.slice(-4)}`,
    allowed_models: [],
    allowed_capabilities: [],
    rpm_limit: null,
    tpm_limit: null,
    store_full_messages: false,
    guardrail_enabled: true,
    is_active: isActive,
    is_system: false,
    expires_at: null,
    last_used_at: null,
    usage_count: 0,
    created_at: '2026-05-18T00:00:00Z',
  }
}

function makeCreated(id: string, plain: string, name = 'auto'): VirtualKeyCreated {
  return { ...makeVKey(id, name), plain_key: plain }
}

function wrapper(): React.FC<{ children: React.ReactNode }> {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }) => React.createElement(QueryClientProvider, { client: qc }, children)
}

beforeEach(() => {
  window.localStorage.clear()
  createKeyMock.mockReset()
  listKeysMock.mockReset()
  listKeysMock.mockResolvedValue([])
})

describe('usePlaygroundVirtualKey', () => {
  test('autoEnsure 在缓存为空时调用 createKey 并写入 v2 缓存', async () => {
    listKeysMock.mockResolvedValueOnce([])
    // 第二次（invalidate 后）已包含新创建的 key
    listKeysMock.mockResolvedValueOnce([makeVKey('k1')])
    createKeyMock.mockResolvedValue(makeCreated('k1', 'sk-gw-PLAIN1'))

    const { result } = renderHook(() => usePlaygroundVirtualKey({ autoEnsure: true }), {
      wrapper: wrapper(),
    })

    await waitFor(() => {
      expect(result.current.selected?.plain).toBe('sk-gw-PLAIN1')
    })
    expect(createKeyMock).toHaveBeenCalledTimes(1)
    expect(result.current.items).toHaveLength(1)
    const persisted = readPersistedV2()
    expect(persisted.v).toBe(2)
    expect(persisted.items[0]?.plain).toBe('sk-gw-PLAIN1')
  })

  test('autoEnsure=false 时不会触发自动创建', async () => {
    createKeyMock.mockResolvedValue(makeCreated('k1', 'sk-gw-PLAIN1'))
    const { result } = renderHook(() => usePlaygroundVirtualKey({ autoEnsure: false }), {
      wrapper: wrapper(),
    })
    await waitFor(() => {
      expect(listKeysMock).toHaveBeenCalled()
    })
    expect(createKeyMock).not.toHaveBeenCalled()
    expect(result.current.selected).toBeNull()
  })

  test('v1 缓存自动迁移到 v2 列表，并保留明文', async () => {
    window.localStorage.setItem(
      STORAGE_KEY_V1,
      JSON.stringify({ v: 1, id: 'old', plain: 'sk-gw-OLD', name: '历史 Key' })
    )
    listKeysMock.mockResolvedValue([makeVKey('old')])

    const { result } = renderHook(() => usePlaygroundVirtualKey({ autoEnsure: false }), {
      wrapper: wrapper(),
    })

    expect(result.current.items).toHaveLength(1)
    expect(result.current.selected?.plain).toBe('sk-gw-OLD')
    expect(window.localStorage.getItem(STORAGE_KEY_V1)).toBeNull()
    const migrated = readPersistedV2()
    expect(migrated.v).toBe(2)
    expect(migrated.items[0]?.id).toBe('old')
    // 服务端确认仍然存在，缓存不变
    await waitFor(() => {
      expect(listKeysMock).toHaveBeenCalled()
    })
    expect(result.current.items).toHaveLength(1)
  })

  test('listKeys 返回中失活或不存在的缓存项会被自动清除', async () => {
    window.localStorage.setItem(
      STORAGE_KEY_V2,
      JSON.stringify({
        v: 2,
        items: [
          { id: 'alive', plain: 'p1', name: 'a', createdAt: '', lastUsedAt: '' },
          { id: 'dead', plain: 'p2', name: 'b', createdAt: '', lastUsedAt: '' },
        ],
        lastSelectedId: 'dead',
      })
    )
    listKeysMock.mockResolvedValue([makeVKey('alive', 'a', true), makeVKey('dead', 'b', false)])
    const { result } = renderHook(() => usePlaygroundVirtualKey({ autoEnsure: false }), {
      wrapper: wrapper(),
    })
    await waitFor(() => {
      expect(result.current.items.map((i) => i.id)).toEqual(['alive'])
    })
    expect(result.current.selected?.id).toBe('alive')
  })

  test('regenerate 把新 Key 插入到列表头部并标记为选中', async () => {
    window.localStorage.setItem(
      STORAGE_KEY_V2,
      JSON.stringify({
        v: 2,
        items: [{ id: 'k1', plain: 'p1', name: 'a', createdAt: '', lastUsedAt: '' }],
        lastSelectedId: 'k1',
      })
    )
    // listKeys 任何时候被调用都返回 k1+k2，避免与 regenerate 时序竞争
    listKeysMock.mockResolvedValue([makeVKey('k1'), makeVKey('k2')])
    createKeyMock.mockResolvedValue(makeCreated('k2', 'sk-gw-NEW'))

    const { result } = renderHook(() => usePlaygroundVirtualKey({ autoEnsure: false }), {
      wrapper: wrapper(),
    })

    // 等初次 listKeys 落定，让校验 effect 先用基线 keys 跑过一次
    await waitFor(() => {
      expect(listKeysMock).toHaveBeenCalled()
    })

    await act(async () => {
      await result.current.regenerate()
    })

    expect(result.current.items.map((i) => i.id)).toEqual(['k2', 'k1'])
    expect(result.current.selected?.id).toBe('k2')
  })

  test('selectKey 切换 lastSelectedId 并影响 selected', () => {
    window.localStorage.setItem(
      STORAGE_KEY_V2,
      JSON.stringify({
        v: 2,
        items: [
          { id: 'k1', plain: 'p1', name: 'a', createdAt: '', lastUsedAt: '' },
          { id: 'k2', plain: 'p2', name: 'b', createdAt: '', lastUsedAt: '' },
        ],
        lastSelectedId: 'k1',
      })
    )
    listKeysMock.mockResolvedValue([makeVKey('k1'), makeVKey('k2')])
    const { result } = renderHook(() => usePlaygroundVirtualKey({ autoEnsure: false }), {
      wrapper: wrapper(),
    })
    expect(result.current.selected?.id).toBe('k1')
    act(() => {
      result.current.selectKey('k2')
    })
    expect(result.current.selected?.id).toBe('k2')
  })

  test('forget(id) 移除单条；forget() 清空全部', async () => {
    window.localStorage.setItem(
      STORAGE_KEY_V2,
      JSON.stringify({
        v: 2,
        items: [
          { id: 'k1', plain: 'p1', name: 'a', createdAt: '', lastUsedAt: '' },
          { id: 'k2', plain: 'p2', name: 'b', createdAt: '', lastUsedAt: '' },
        ],
        lastSelectedId: 'k2',
      })
    )
    listKeysMock.mockResolvedValue([makeVKey('k1'), makeVKey('k2')])
    const { result } = renderHook(() => usePlaygroundVirtualKey({ autoEnsure: false }), {
      wrapper: wrapper(),
    })
    // 等 listKeys 落地，避免后续 forget 操作被校验 effect 干扰
    await waitFor(() => {
      expect(listKeysMock).toHaveBeenCalled()
    })
    act(() => {
      result.current.forget('k2')
    })
    expect(result.current.items.map((i) => i.id)).toEqual(['k1'])
    expect(result.current.selected?.id).toBe('k1')
    act(() => {
      result.current.forget()
    })
    expect(result.current.items).toEqual([])
    expect(result.current.selected).toBeNull()
  })
})
