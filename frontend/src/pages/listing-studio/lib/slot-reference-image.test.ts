/**
 * slot-reference-image 纯函数单测
 */

import { describe, it, expect } from 'vitest'

import { resolveProductSourceImageUrl, resolveSlotReferenceImage } from './slot-reference-image'

describe('resolveProductSourceImageUrl', () => {
  it('手动参考图优先', () => {
    expect(resolveProductSourceImageUrl('https://manual.jpg', ['https://input.jpg'])).toBe(
      'https://manual.jpg'
    )
  })

  it('回退到输入区原图', () => {
    expect(resolveProductSourceImageUrl(undefined, ['https://input.jpg'])).toBe('https://input.jpg')
  })

  it('皆无则 null', () => {
    expect(resolveProductSourceImageUrl(undefined, [])).toBeNull()
  })
})

describe('resolveSlotReferenceImage', () => {
  it('显式 reference 最高优先级', () => {
    expect(
      resolveSlotReferenceImage({
        mode: 'current',
        slot: 2,
        explicitReferenceUrl: 'https://explicit.jpg',
        currentSlotUrl: 'https://current.jpg',
      })
    ).toBe('https://explicit.jpg')
  })

  it('current 模式用当前槽图', () => {
    expect(
      resolveSlotReferenceImage({
        mode: 'current',
        slot: 3,
        currentSlotUrl: 'https://gen3.jpg',
        sourceImageUrl: 'https://source.jpg',
      })
    ).toBe('https://gen3.jpg')
  })

  it('chain 模式 slot2 用 slot1 生成图', () => {
    expect(
      resolveSlotReferenceImage({
        mode: 'chain',
        slot: 2,
        sourceImageUrl: 'https://source.jpg',
        slot1GeneratedUrl: 'https://white.jpg',
      })
    ).toBe('https://white.jpg')
  })
})
