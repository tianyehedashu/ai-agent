import { describe, expect, it } from 'vitest'

import { parseImageGenerationResponse, parseVideoGenerationResponse } from './media-parse'

describe('media-parse', () => {
  it('parses OpenAI image response', () => {
    const items = parseImageGenerationResponse({
      data: [{ url: 'https://example.com/a.png', revised_prompt: 'x' }],
    })
    expect(items).toHaveLength(1)
    expect(items[0]?.url).toBe('https://example.com/a.png')
  })

  it('parses video url variants', () => {
    expect(parseVideoGenerationResponse({ url: 'https://v.example/x.mp4' }).url).toBe(
      'https://v.example/x.mp4'
    )
    expect(parseVideoGenerationResponse({ video: { url: 'https://v.example/y.mp4' } }).url).toBe(
      'https://v.example/y.mp4'
    )
  })
})
