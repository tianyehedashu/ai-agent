import { describe, expect, it } from 'vitest'

import {
  inferImageGenProviderFromModelName,
  resolvePlaygroundImageGenProvider,
} from './resolve-playground-image-gen-provider'

describe('resolvePlaygroundImageGenProvider', () => {
  it('prefers model provider over credential filter', () => {
    expect(resolvePlaygroundImageGenProvider('openai', 'volcengine')).toBe('volcengine')
  })

  it('falls back to credential when model provider missing', () => {
    expect(resolvePlaygroundImageGenProvider('volcengine', undefined)).toBe('volcengine')
  })

  it('infers volcengine from ep- model name', () => {
    expect(resolvePlaygroundImageGenProvider(undefined, undefined, 'ep-image-1')).toBe('volcengine')
    expect(inferImageGenProviderFromModelName('EP-FOO')).toBe('volcengine')
  })
})
