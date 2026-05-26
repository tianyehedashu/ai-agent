import { describe, expect, it } from 'vitest'

import { REGISTRY_ABILITY_FILTER_OPTIONS } from './registry-ability-filter-select'

/** backend domains.gateway.domain.registry_model_types.REGISTRY_ABILITY_FILTER_VALUES */
const BACKEND_REGISTRY_ABILITY_FILTER_VALUES = [
  'text',
  'image',
  'image_gen',
  'video',
  'chat',
  'embedding',
  'video_generation',
  'moderation',
  'audio_transcription',
  'audio_speech',
  'rerank',
] as const

describe('REGISTRY_ABILITY_FILTER_OPTIONS', () => {
  it('matches backend REGISTRY_ABILITY_FILTER_VALUES', () => {
    expect(REGISTRY_ABILITY_FILTER_OPTIONS.map((o) => o.value)).toEqual([
      ...BACKEND_REGISTRY_ABILITY_FILTER_VALUES,
    ])
  })

  it('assigns a label to every option', () => {
    for (const opt of REGISTRY_ABILITY_FILTER_OPTIONS) {
      expect(opt.label.length).toBeGreaterThan(0)
    }
  })
})
