import { describe, expect, it } from 'vitest'

import { inferUpstreamModelTypes, resolveUpstreamModelTypes } from './infer-model-types'

describe('inferUpstreamModelTypes', () => {
  it('marks embedding as non-importable', () => {
    expect(inferUpstreamModelTypes('openai', 'text-embedding-3-small')).toEqual([])
  })

  it('defaults to text when server hint unavailable', () => {
    expect(inferUpstreamModelTypes('volcengine', 'kimi-k2.6')).toEqual(['text'])
    expect(inferUpstreamModelTypes('openai', 'some-custom-model')).toEqual(['text'])
  })
})

describe('resolveUpstreamModelTypes', () => {
  it('prefers server inferred_model_types', () => {
    expect(
      resolveUpstreamModelTypes(
        { id: 'kimi-k2.6', inferred_model_types: ['text', 'image'] },
        'volcengine'
      )
    ).toEqual(['text', 'image'])
  })

  it('honors empty server list as non-importable', () => {
    expect(
      resolveUpstreamModelTypes(
        { id: 'text-embedding-3-small', inferred_model_types: [] },
        'openai'
      )
    ).toEqual([])
  })

  it('falls back to client infer when server field omitted', () => {
    expect(resolveUpstreamModelTypes({ id: 'gpt-4o-mini' }, 'openai')).toEqual(['text'])
  })
})
