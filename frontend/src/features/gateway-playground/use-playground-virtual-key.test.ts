/**
 * usePlaygroundVirtualKey 行为单测
 */

import React, { act } from 'react'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, test, vi } from 'vitest'

import type { VirtualKey } from '@/api/gateway'
import {
  LEGACY_STORAGE_KEYS,
  resetPlaygroundVkeyLegacyMigration,
} from '@/features/gateway-playground/playground-vkey-persist'
import {
  readPersistedPlaygroundVkeySelection,
  usePlaygroundVkeySelectionStore,
} from '@/stores/playground-vkey-selection'

import { usePlaygroundVirtualKey } from './use-playground-virtual-key'

const listKeysMock = vi.fn((): Promise<VirtualKey[]> => Promise.resolve([]))
const revealKeyMock = vi.fn(
  (_id: string): Promise<{ plain_key: string }> =>
    Promise.reject(new Error('revealKeyMock not configured'))
)

vi.mock('@/api/gateway', () => ({
  gatewayApi: {
    listKeys: () => listKeysMock(),
    revealKey: (id: string) => revealKeyMock(id),
  },
}))

const STORAGE_KEY_V1 = LEGACY_STORAGE_KEYS[0]
const STORAGE_KEY_V2 = LEGACY_STORAGE_KEYS[1]

function makeVKey(id: string, name = 'k', overrides: Partial<VirtualKey> = {}): VirtualKey {
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
    is_active: true,
    is_system: false,
    expires_at: null,
    last_used_at: null,
    usage_count: 0,
    created_at: '2026-05-18T00:00:00Z',
    ...overrides,
  }
}

function wrapper(): React.FC<{ children: React.ReactNode }> {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }) => React.createElement(QueryClientProvider, { client: qc }, children)
}

beforeEach(() => {
  window.localStorage.clear()
  resetPlaygroundVkeyLegacyMigration()
  usePlaygroundVkeySelectionStore.setState({ lastSelectedId: null })
  listKeysMock.mockReset()
  revealKeyMock.mockReset()
  listKeysMock.mockResolvedValue([])
})

describe('usePlaygroundVirtualKey', () => {
  test('过滤掉 system 与 inactive Key', async () => {
    listKeysMock.mockResolvedValue([
      makeVKey('k1', 'normal'),
      makeVKey('sys', 's', { is_system: true }),
      makeVKey('dead', 'd', { is_active: false }),
    ])
    revealKeyMock.mockResolvedValue({ plain_key: 'sk-gw-PLAIN-K1' })

    const { result } = renderHook(() => usePlaygroundVirtualKey(), { wrapper: wrapper() })

    await waitFor(() => {
      expect(result.current.keys.map((k) => k.id)).toEqual(['k1'])
    })
  })

  test('首次进入且无持久化选中时，自动选第一把可用 Key 并 reveal 明文', async () => {
    listKeysMock.mockResolvedValue([makeVKey('k1'), makeVKey('k2')])
    revealKeyMock.mockResolvedValue({ plain_key: 'sk-gw-FIRST' })

    const { result } = renderHook(() => usePlaygroundVirtualKey(), { wrapper: wrapper() })

    await waitFor(() => {
      expect(result.current.selectedKeyId).toBe('k1')
    })
    await waitFor(() => {
      expect(result.current.plain).toBe('sk-gw-FIRST')
    })
    expect(revealKeyMock).toHaveBeenCalledWith('k1')
    expect(readPersistedPlaygroundVkeySelection()).toBe('k1')
  })

  test('selectKey 切换：reveal 新 Key 明文,持久化 id', async () => {
    listKeysMock.mockResolvedValue([makeVKey('k1'), makeVKey('k2')])
    revealKeyMock.mockImplementation((id: string) => Promise.resolve({ plain_key: `plain-${id}` }))

    const { result } = renderHook(() => usePlaygroundVirtualKey(), { wrapper: wrapper() })

    await waitFor(() => {
      expect(result.current.plain).toBe('plain-k1')
    })

    act(() => {
      result.current.selectKey('k2')
    })

    expect(result.current.plain).toBeNull()
    await waitFor(() => {
      expect(result.current.plain).toBe('plain-k2')
    })
    expect(readPersistedPlaygroundVkeySelection()).toBe('k2')
  })

  test('selectKey(null) 清空选中与明文', async () => {
    listKeysMock.mockResolvedValue([makeVKey('k1')])
    revealKeyMock.mockResolvedValue({ plain_key: 'sk-gw-K1' })

    const { result } = renderHook(() => usePlaygroundVirtualKey(), { wrapper: wrapper() })
    await waitFor(() => {
      expect(result.current.plain).toBe('sk-gw-K1')
    })

    act(() => {
      result.current.selectKey(null)
    })

    expect(result.current.selectedKey).toBeNull()
    expect(result.current.plain).toBeNull()
    expect(readPersistedPlaygroundVkeySelection()).toBeNull()
  })

  test('服务端撤销当前选中 Key 时,本地选中被自动清空', async () => {
    usePlaygroundVkeySelectionStore.setState({ lastSelectedId: 'gone' })
    listKeysMock.mockResolvedValue([makeVKey('alive')])
    revealKeyMock.mockResolvedValue({ plain_key: 'sk-gw-ALIVE' })

    const { result } = renderHook(() => usePlaygroundVirtualKey(), { wrapper: wrapper() })

    await waitFor(() => {
      expect(result.current.selectedKeyId).toBe('alive')
    })
    await waitFor(() => {
      expect(result.current.plain).toBe('sk-gw-ALIVE')
    })
  })

  test('preferKeyId 仅在列表包含该 id 时选中', async () => {
    listKeysMock.mockResolvedValue([makeVKey('k1'), makeVKey('k2')])
    revealKeyMock.mockResolvedValue({ plain_key: 'sk-gw-K2' })

    const { result } = renderHook(() => usePlaygroundVirtualKey({ preferKeyId: 'k2' }), {
      wrapper: wrapper(),
    })

    await waitFor(() => {
      expect(result.current.selectedKeyId).toBe('k2')
    })
    expect(revealKeyMock).toHaveBeenCalledWith('k2')
  })

  test('preferKeyId 不在列表时不强行选中', async () => {
    listKeysMock.mockResolvedValue([makeVKey('k1')])
    revealKeyMock.mockResolvedValue({ plain_key: 'sk-gw-K1' })

    const { result } = renderHook(() => usePlaygroundVirtualKey({ preferKeyId: 'missing' }), {
      wrapper: wrapper(),
    })

    await waitFor(() => {
      expect(result.current.selectedKeyId).toBe('k1')
    })
    expect(revealKeyMock).toHaveBeenCalledWith('k1')
  })

  test('bootstrap 命中时跳过 reveal 并直接返回明文', async () => {
    listKeysMock.mockResolvedValue([makeVKey('k1')])
    revealKeyMock.mockResolvedValue({ plain_key: 'should-not-call' })

    const { result } = renderHook(
      () => usePlaygroundVirtualKey({ plain: 'sk-gw-BOOT', keyId: 'k1' }),
      { wrapper: wrapper() }
    )

    await waitFor(() => {
      expect(result.current.plain).toBe('sk-gw-BOOT')
    })
    expect(revealKeyMock).not.toHaveBeenCalled()
    expect(result.current.revealError).toBeNull()
  })

  test('reveal 失败时暴露 revealError 并保持 plain 为 null', async () => {
    listKeysMock.mockResolvedValue([makeVKey('k1')])
    revealKeyMock.mockRejectedValue(new Error('400 decrypt failed'))

    const { result } = renderHook(() => usePlaygroundVirtualKey(), { wrapper: wrapper() })

    await waitFor(() => {
      expect(result.current.revealError?.message).toBe('400 decrypt failed')
    })
    expect(result.current.plain).toBeNull()
  })

  test('迁移 v2 缓存:抽取 lastSelectedId,丢弃明文,清掉旧 key', async () => {
    window.localStorage.setItem(
      STORAGE_KEY_V2,
      JSON.stringify({
        v: 2,
        items: [
          { id: 'm1', plain: 'should-be-dropped', name: 'old', createdAt: '', lastUsedAt: '' },
        ],
        lastSelectedId: 'm1',
      })
    )
    listKeysMock.mockResolvedValue([makeVKey('m1', 'migrated'), makeVKey('m2')])
    revealKeyMock.mockResolvedValue({ plain_key: 'sk-gw-FROM-SERVER' })

    const { result } = renderHook(() => usePlaygroundVirtualKey(), { wrapper: wrapper() })

    await waitFor(() => {
      expect(window.localStorage.getItem(STORAGE_KEY_V2)).toBeNull()
    })
    await waitFor(() => {
      expect(readPersistedPlaygroundVkeySelection()).toBe('m1')
    })

    await waitFor(() => {
      expect(result.current.selectedKeyId).toBe('m1')
    })
    await waitFor(() => {
      expect(result.current.plain).toBe('sk-gw-FROM-SERVER')
    })
    expect(revealKeyMock).toHaveBeenCalledWith('m1')
  })

  test('迁移 v1 单把缓存', async () => {
    window.localStorage.setItem(
      STORAGE_KEY_V1,
      JSON.stringify({ v: 1, id: 'legacy', plain: 'dropped', name: 'old' })
    )
    listKeysMock.mockResolvedValue([makeVKey('legacy')])
    revealKeyMock.mockResolvedValue({ plain_key: 'sk-gw-LEGACY' })

    const { result } = renderHook(() => usePlaygroundVirtualKey(), { wrapper: wrapper() })

    await waitFor(() => {
      expect(window.localStorage.getItem(STORAGE_KEY_V1)).toBeNull()
    })
    await waitFor(() => {
      expect(readPersistedPlaygroundVkeySelection()).toBe('legacy')
    })
    await waitFor(() => {
      expect(result.current.plain).toBe('sk-gw-LEGACY')
    })
  })
})
