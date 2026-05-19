import { describe, expect, it } from 'vitest'

import {
  filterModelsByMode,
  modelSupportsImageGen,
  modelSupportsVideoGen,
  type ModelCandidate,
} from './playground-mode-filter'

const base = (overrides: Partial<ModelCandidate>): ModelCandidate => ({
  name: 'm',
  scope: 'team',
  status: null,
  capability: 'chat',
  ...overrides,
})

describe('playground-mode-filter', () => {
  it('filters chat models', () => {
    const models = [
      base({ name: 'a', capability: 'chat' }),
      base({ name: 'b', capability: 'video_generation' }),
    ]
    expect(filterModelsByMode(models, 'chat').map((m) => m.name)).toEqual(['a'])
  })

  it('filters vision models', () => {
    const models = [
      base({ name: 'v', selector_capabilities: { supports_vision: true } }),
      base({ name: 't', capability: 'chat' }),
    ]
    expect(filterModelsByMode(models, 'vision').map((m) => m.name)).toEqual(['v'])
  })

  it('detects image_gen via capability or model_types', () => {
    expect(modelSupportsImageGen(base({ capability: 'image' }))).toBe(true)
    expect(modelSupportsImageGen(base({ model_types: ['image_gen'] }))).toBe(true)
  })

  it('detects video_gen via capability or model_types', () => {
    expect(modelSupportsVideoGen(base({ capability: 'video_generation' }))).toBe(true)
    expect(modelSupportsVideoGen(base({ model_types: ['video'] }))).toBe(true)
  })
})
