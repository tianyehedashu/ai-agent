/**
 * useCopyToClipboard / useCopyToClipboardKeyed 单测
 */

import { act } from 'react'

import { renderHook } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { useCopyToClipboard, useCopyToClipboardKeyed } from './use-copy-to-clipboard'

vi.mock('@/lib/utils', () => ({
  copyToClipboard: vi.fn().mockResolvedValue(undefined),
}))

describe('useCopyToClipboard', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('初始 copied 为 false', () => {
    const { result } = renderHook(() => useCopyToClipboard())
    expect(result.current[1]).toBe(false)
  })

  it('copy 后 copied 为 true，约 1.5s 后恢复 false', async () => {
    const { result } = renderHook(() => useCopyToClipboard())
    await act(async () => {
      await result.current[0]('hello')
    })
    const { copyToClipboard } = await import('@/lib/utils')
    expect(copyToClipboard).toHaveBeenCalledWith('hello')
    expect(result.current[1]).toBe(true)
    act(() => {
      vi.advanceTimersByTime(1500)
    })
    expect(result.current[1]).toBe(false)
  })
})

describe('useCopyToClipboardKeyed', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('初始 copiedKey 为 null', () => {
    const { result } = renderHook(() => useCopyToClipboardKeyed())
    expect(result.current[1]).toBe(null)
  })

  it('copy(text, key) 后 copiedKey 为 key', async () => {
    const { result } = renderHook(() => useCopyToClipboardKeyed())
    await act(async () => {
      await result.current[0]('text', 3)
    })
    const { copyToClipboard } = await import('@/lib/utils')
    expect(copyToClipboard).toHaveBeenCalledWith('text')
    expect(result.current[1]).toBe(3)
  })
})
