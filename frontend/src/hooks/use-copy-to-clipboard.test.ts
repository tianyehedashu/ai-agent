/**
 * useCopyToClipboard / useCopyToClipboardKeyed 单测
 */

import { act } from 'react'

import { renderHook } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { useCopyToClipboard, useCopyToClipboardKeyed } from './use-copy-to-clipboard'

describe('useCopyToClipboard', () => {
  const writeText = vi.fn()

  beforeEach(() => {
    vi.useFakeTimers()
    Object.assign(navigator, { clipboard: { writeText } })
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
    writeText.mockResolvedValue(undefined)
    const { result } = renderHook(() => useCopyToClipboard())
    await act(async () => {
      await result.current[0]('hello')
    })
    expect(writeText).toHaveBeenCalledWith('hello')
    expect(result.current[1]).toBe(true)
    act(() => {
      vi.advanceTimersByTime(1500)
    })
    expect(result.current[1]).toBe(false)
  })
})

describe('useCopyToClipboardKeyed', () => {
  const writeText = vi.fn()

  beforeEach(() => {
    vi.useFakeTimers()
    Object.assign(navigator, { clipboard: { writeText } })
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
    writeText.mockResolvedValue(undefined)
    const { result } = renderHook(() => useCopyToClipboardKeyed())
    await act(async () => {
      await result.current[0]('text', 3)
    })
    expect(writeText).toHaveBeenCalledWith('text')
    expect(result.current[1]).toBe(3)
  })
})
