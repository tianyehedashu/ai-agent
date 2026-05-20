/**
 * capabilities 配置 derive / fallback 单测
 */

import { describe, it, expect } from 'vitest'

import {
  deriveCapabilitiesFromApi,
  getFallbackCapabilitiesConfig,
} from './use-listing-studio-capabilities'

describe('getFallbackCapabilitiesConfig', () => {
  it('包含 executionLayers 三层结构', () => {
    const cfg = getFallbackCapabilitiesConfig()
    expect(cfg.executionLayers).toHaveLength(3)
    expect(cfg.capabilityOrder.length).toBeGreaterThan(0)
  })
})

describe('deriveCapabilitiesFromApi', () => {
  it('从 API 能力列表构建 config', () => {
    const cfg = deriveCapabilitiesFromApi(
      [
        {
          id: 'image_analysis',
          name: '图片分析',
          sort_order: 1,
          model_type: 'image',
          output_key: 'image_descriptions',
        },
      ],
      [['image_analysis']]
    )
    expect(cfg.capabilityOrder).toEqual(['image_analysis'])
    expect(cfg.outputKeys.image_analysis).toBe('image_descriptions')
    expect(cfg.executionLayers).toEqual([['image_analysis']])
  })

  it('execution_layers 为空时回退 fallback 分层', () => {
    const cfg = deriveCapabilitiesFromApi([{ id: 'image_analysis', name: '图片分析' }], [])
    expect(cfg.executionLayers).toEqual(getFallbackCapabilitiesConfig().executionLayers)
  })
})
