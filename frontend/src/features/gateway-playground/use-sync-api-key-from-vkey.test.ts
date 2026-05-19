/**
 * useSyncApiKeyFromVkey 行为单测：保证「取消选中 Key 时清空 apiKey」不再回归。
 */

import { act, useRef, useState } from 'react'

import { renderHook } from '@testing-library/react'
import { describe, expect, test } from 'vitest'

import { useSyncApiKeyFromVkey } from './use-sync-api-key-from-vkey'

interface HookProps {
  plain: string | null
  selectedKeyId: string | null
  initialUserEdited?: boolean
}

interface HookValue {
  apiKey: string
  setApiKey: (value: string) => void
  setUserEdited: (value: boolean) => void
}

function useHarness({ plain, selectedKeyId, initialUserEdited = false }: HookProps): HookValue {
  const [apiKey, setApiKey] = useState('')
  const userEditedRef = useRef(initialUserEdited)
  useSyncApiKeyFromVkey({ plain, selectedKeyId, userEditedRef, setApiKey })
  return {
    apiKey,
    setApiKey,
    setUserEdited: (value: boolean) => {
      userEditedRef.current = value
    },
  }
}

function setup(initial: HookProps): ReturnType<typeof renderHook<HookValue, HookProps>> {
  return renderHook<HookValue, HookProps>((props) => useHarness(props), { initialProps: initial })
}

describe('useSyncApiKeyFromVkey', () => {
  test('reveal 明文到达时写入 apiKey', () => {
    const { result, rerender } = setup({ plain: null, selectedKeyId: 'k1' })
    expect(result.current.apiKey).toBe('')

    rerender({ plain: 'sk-gw-K1', selectedKeyId: 'k1' })
    expect(result.current.apiKey).toBe('sk-gw-K1')
  })

  test('用户手动编辑后 reveal 不再覆盖', () => {
    const { result, rerender } = setup({ plain: 'sk-gw-K1', selectedKeyId: 'k1' })
    expect(result.current.apiKey).toBe('sk-gw-K1')

    act(() => {
      result.current.setUserEdited(true)
      result.current.setApiKey('manual-paste')
    })
    rerender({ plain: 'sk-gw-K2', selectedKeyId: 'k2' })
    expect(result.current.apiKey).toBe('manual-paste')
  })

  test('取消选中（selectedKeyId 变为 null）会清空 apiKey', () => {
    const { result, rerender } = setup({ plain: 'sk-gw-K1', selectedKeyId: 'k1' })
    expect(result.current.apiKey).toBe('sk-gw-K1')

    rerender({ plain: null, selectedKeyId: null })
    expect(result.current.apiKey).toBe('')
  })

  test('选中切换时 reveal 中（plain 暂为 null）不会误清空', () => {
    const { result, rerender } = setup({ plain: 'sk-gw-K1', selectedKeyId: 'k1' })
    expect(result.current.apiKey).toBe('sk-gw-K1')

    rerender({ plain: null, selectedKeyId: 'k2' })
    expect(result.current.apiKey).toBe('sk-gw-K1')

    rerender({ plain: 'sk-gw-K2', selectedKeyId: 'k2' })
    expect(result.current.apiKey).toBe('sk-gw-K2')
  })

  test('用户手动编辑后取消选中也保留用户输入', () => {
    const { result, rerender } = setup({ plain: 'sk-gw-K1', selectedKeyId: 'k1' })
    act(() => {
      result.current.setUserEdited(true)
      result.current.setApiKey('manual-paste')
    })
    rerender({ plain: null, selectedKeyId: null })
    expect(result.current.apiKey).toBe('manual-paste')
  })
})
