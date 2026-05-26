import { describe, expect, it } from 'vitest'

import {
  defaultImageGenSizeForProvider,
  imageGenPresetBySize,
  imageGenPresetsForProvider,
  OPENAI_IMAGE_GEN_PRESETS,
  VOLCENGINE_IMAGE_GEN_PRESETS,
  VOLCENGINE_MIN_IMAGE_PIXELS,
} from './image-gen-size-presets'

describe('image-gen-size-presets', () => {
  it('exposes OpenAI three-aspect presets', () => {
    expect(OPENAI_IMAGE_GEN_PRESETS.map((p) => p.aspect)).toEqual(['1:1', '9:16', '16:9'])
    expect(defaultImageGenSizeForProvider('openai')).toBe('1024x1024')
  })

  it('volcengine presets meet minimum pixels', () => {
    for (const p of VOLCENGINE_IMAGE_GEN_PRESETS) {
      expect(p.width * p.height).toBeGreaterThanOrEqual(VOLCENGINE_MIN_IMAGE_PIXELS)
    }
    expect(imageGenPresetsForProvider('volcengine')).toHaveLength(6)
    expect(defaultImageGenSizeForProvider('Volcengine')).toBe('1920x1920')
  })

  it('resolves preset by size', () => {
    expect(imageGenPresetBySize('volcengine', '2944x1664')?.label).toBe('横版')
    expect(imageGenPresetBySize('openai', '1024x1792')?.aspect).toBe('9:16')
  })
})
