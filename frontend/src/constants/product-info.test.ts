/**
 * product-info 常量验证：依赖关系、输入字段映射与能力列表一致性
 */

import { describe, it, expect } from 'vitest'

import {
  CAPABILITY_ORDER,
  CAPABILITY_NAMES,
  CAPABILITY_DEPENDENCIES,
  CAPABILITY_INPUT_FIELDS,
  OUTPUT_KEYS,
  INPUT_FIELDS,
} from './product-info'

describe('CAPABILITY_ORDER', () => {
  it('包含 5 个能力', () => {
    expect(CAPABILITY_ORDER).toHaveLength(5)
  })

  it('包含所有预期能力', () => {
    const ids = [...CAPABILITY_ORDER]
    expect(ids).toContain('image_analysis')
    expect(ids).toContain('product_link_analysis')
    expect(ids).toContain('competitor_link_analysis')
    expect(ids).toContain('video_script')
    expect(ids).toContain('image_gen_prompts')
  })
})

describe('CAPABILITY_NAMES', () => {
  it('每个 CAPABILITY_ORDER 成员都有名称', () => {
    for (const id of CAPABILITY_ORDER) {
      expect(CAPABILITY_NAMES[id]).toBeDefined()
      expect(CAPABILITY_NAMES[id].length).toBeGreaterThan(0)
    }
  })
})

describe('CAPABILITY_DEPENDENCIES', () => {
  it('每个 CAPABILITY_ORDER 成员都有依赖定义', () => {
    for (const id of CAPABILITY_ORDER) {
      expect(CAPABILITY_DEPENDENCIES[id]).toBeDefined()
      expect(Array.isArray(CAPABILITY_DEPENDENCIES[id])).toBe(true)
    }
  })

  it('依赖引用的 capability_id 都在 CAPABILITY_ORDER 中', () => {
    for (const [capId, deps] of Object.entries(CAPABILITY_DEPENDENCIES)) {
      expect(CAPABILITY_ORDER).toContain(capId)
      for (const dep of deps) {
        expect(CAPABILITY_ORDER).toContain(dep)
      }
    }
  })

  it('无循环依赖（被依赖的步骤序号 < 当前步骤序号）', () => {
    for (const [capId, deps] of Object.entries(CAPABILITY_DEPENDENCIES)) {
      const capIndex = CAPABILITY_ORDER.indexOf(capId as (typeof CAPABILITY_ORDER)[number])
      for (const dep of deps) {
        const depIndex = CAPABILITY_ORDER.indexOf(dep as (typeof CAPABILITY_ORDER)[number])
        expect(depIndex).toBeLessThan(capIndex)
      }
    }
  })

  it('image_analysis / product_link / competitor_link 无依赖', () => {
    expect(CAPABILITY_DEPENDENCIES.image_analysis).toEqual([])
    expect(CAPABILITY_DEPENDENCIES.product_link_analysis).toEqual([])
    expect(CAPABILITY_DEPENDENCIES.competitor_link_analysis).toEqual([])
  })

  it('video_script 依赖 product_link 和 competitor_link', () => {
    expect(CAPABILITY_DEPENDENCIES.video_script).toContain('product_link_analysis')
    expect(CAPABILITY_DEPENDENCIES.video_script).toContain('competitor_link_analysis')
  })

  it('image_gen_prompts 依赖 product_link 和 video_script', () => {
    expect(CAPABILITY_DEPENDENCIES.image_gen_prompts).toContain('product_link_analysis')
    expect(CAPABILITY_DEPENDENCIES.image_gen_prompts).toContain('video_script')
  })
})

describe('CAPABILITY_INPUT_FIELDS', () => {
  it('每个 CAPABILITY_ORDER 成员都有输入字段定义', () => {
    for (const id of CAPABILITY_ORDER) {
      expect(CAPABILITY_INPUT_FIELDS[id]).toBeDefined()
      expect(Array.isArray(CAPABILITY_INPUT_FIELDS[id])).toBe(true)
    }
  })

  it('引用的字段 key 在 INPUT_FIELDS 或是 image_urls', () => {
    const knownKeys = new Set<string>(INPUT_FIELDS.map((f) => f.key))
    knownKeys.add('image_urls')

    for (const fields of Object.values(CAPABILITY_INPUT_FIELDS)) {
      for (const f of fields) {
        expect(knownKeys.has(f)).toBe(true)
      }
    }
  })
})

describe('OUTPUT_KEYS', () => {
  it('每个 CAPABILITY_ORDER 成员都有 output key 定义', () => {
    for (const id of CAPABILITY_ORDER) {
      expect(OUTPUT_KEYS[id]).toBeDefined()
      expect(OUTPUT_KEYS[id].length).toBeGreaterThan(0)
    }
  })
})
