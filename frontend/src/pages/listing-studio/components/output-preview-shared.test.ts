/**
 * output-preview-shared 纯函数单测
 */

import { describe, it, expect } from 'vitest'

import type { ProductImageGenTask } from '@/types/listing-studio'

import { getFivePointDescription, pickLatestEightImages } from './output-preview-shared'

describe('getFivePointDescription', () => {
  it('从 bullet_points 解析最多 5 条', () => {
    expect(getFivePointDescription({ bullet_points: ['a', 'b', 'c', 'd', 'e', 'f'] })).toEqual([
      'a',
      'b',
      'c',
      'd',
      'e',
    ])
  })

  it('无匹配字段时返回空数组', () => {
    expect(getFivePointDescription(null)).toEqual([])
    expect(getFivePointDescription({ title: 'x' })).toEqual([])
  })

  it('从 raw_text 按行解析', () => {
    expect(getFivePointDescription({ raw_text: '- 第一点\n* 第二点' })).toEqual([
      '第一点',
      '第二点',
    ])
  })
})

describe('pickLatestEightImages', () => {
  const tasks: ProductImageGenTask[] = [
    {
      id: '1',
      job_id: 'job-a',
      status: 'completed',
      prompts: [],
      result_images: [{ slot: 1, url: 'https://a/1.png' }],
      error_message: null,
      created_at: '2026-01-02',
    },
    {
      id: '2',
      job_id: 'job-b',
      status: 'completed',
      prompts: [],
      result_images: [{ slot: 1, url: 'https://b/1.png' }],
      error_message: null,
      created_at: '2026-01-01',
    },
  ]

  it('优先匹配 job_id', () => {
    expect(pickLatestEightImages(tasks, 'job-a')).toEqual([{ slot: 1, url: 'https://a/1.png' }])
  })

  it('无 job 匹配时取第一条有图任务', () => {
    expect(pickLatestEightImages(tasks, null)).toEqual([{ slot: 1, url: 'https://a/1.png' }])
  })

  it('无任务时返回 null', () => {
    expect(pickLatestEightImages([], 'job-a')).toBeNull()
  })
})
