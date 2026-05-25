/**
 * output-preview-shared 纯函数单测
 */

import { describe, it, expect } from 'vitest'

import type { ProductImageGenTask } from '@/types/listing-studio'

import {
  getFivePointDescription,
  mergedImagesToSlotArray,
  pickLatestEightImages,
} from './output-preview-shared'

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

  it('无 job 匹配时取有图任务', () => {
    expect(pickLatestEightImages(tasks, null)).toEqual([{ slot: 1, url: 'https://a/1.png' }])
  })

  it('无任务时返回 null', () => {
    expect(pickLatestEightImages([], 'job-a')).toBeNull()
  })

  it('跨 task 按槽合并，新 task 仅更新单槽', () => {
    const mergedTasks: ProductImageGenTask[] = [
      {
        id: 'regen-3',
        job_id: 'job-a',
        status: 'completed',
        prompts: [],
        result_images: [{ slot: 3, url: 'https://a/3-new.png' }],
        error_message: null,
        created_at: '2026-01-03',
      },
      {
        id: 'batch-1',
        job_id: 'job-a',
        status: 'completed',
        prompts: [],
        result_images: [
          { slot: 1, url: 'https://a/1.png' },
          { slot: 2, url: 'https://a/2.png' },
          { slot: 3, url: 'https://a/3-old.png' },
        ],
        error_message: null,
        created_at: '2026-01-02',
      },
    ]
    expect(pickLatestEightImages(mergedTasks, 'job-a')).toEqual([
      { slot: 1, url: 'https://a/1.png' },
      { slot: 2, url: 'https://a/2.png' },
      { slot: 3, url: 'https://a/3-new.png' },
    ])
  })
})

describe('mergedImagesToSlotArray', () => {
  it('转为 8 槽数组', () => {
    expect(
      mergedImagesToSlotArray([
        { slot: 1, url: 'https://a/1.png' },
        { slot: 3, url: 'https://a/3.png' },
      ])
    ).toEqual(['https://a/1.png', null, 'https://a/3.png', null, null, null, null, null])
  })
})
