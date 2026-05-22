import { describe, expect, it } from 'vitest'

import { inferUpstreamModelTypes } from './infer-model-types'

describe('inferUpstreamModelTypes', () => {
  it('infers vision chat models', () => {
    expect(inferUpstreamModelTypes('openai', 'gpt-4o-mini')).toEqual(['text', 'image'])
  })

  it('infers image gen', () => {
    expect(inferUpstreamModelTypes('openai', 'dall-e-3')).toEqual(['image_gen'])
  })

  it('infers video', () => {
    expect(inferUpstreamModelTypes('openai', 'sora-2')).toEqual(['video'])
  })

  it('marks embedding as non-importable', () => {
    expect(inferUpstreamModelTypes('openai', 'text-embedding-3-small')).toEqual([])
  })

  it('defaults to text', () => {
    expect(inferUpstreamModelTypes('openai', 'some-custom-model')).toEqual(['text'])
  })
})
