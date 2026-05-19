import { describe, expect, it } from 'vitest'

import { isImageGenRaw, isVideoGenRaw, safeStringify } from './playground-raw-response'

describe('playground-raw-response', () => {
  it('isImageGenRaw 窄化 image_gen', () => {
    expect(isImageGenRaw({ type: 'image_gen', items: [] })).toBe(true)
    expect(isImageGenRaw({ type: 'video_gen', url: 'x' })).toBe(false)
    expect(isImageGenRaw(null)).toBe(false)
    expect(isImageGenRaw({})).toBe(false)
  })

  it('isVideoGenRaw 窄化 video_gen', () => {
    expect(isVideoGenRaw({ type: 'video_gen', url: 'https://x' })).toBe(true)
    expect(isVideoGenRaw({ type: 'image_gen', items: [] })).toBe(false)
    expect(isVideoGenRaw(undefined)).toBe(false)
  })

  it('safeStringify 处理 null 与循环引用', () => {
    expect(safeStringify(null)).toBe('（无）')
    expect(safeStringify({ a: 1 })).toContain('"a": 1')
    const circular: { self?: unknown } = {}
    circular.self = circular
    expect(safeStringify(circular)).toBe('[unserializable]')
  })
})
