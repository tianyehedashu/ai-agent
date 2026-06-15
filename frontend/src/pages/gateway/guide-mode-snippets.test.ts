import { describe, expect, it } from 'vitest'

import { buildMediaModeSnippets } from '@/pages/gateway/guide-mode-snippets'
import { buildGuideSnippets } from '@/pages/gateway/guide-snippets'

const BASE = 'https://gateway.example.com/api/v1/openai/v1'
const KEY = 'sk-gw-test-key'
const MODEL = 'test-model'

describe('buildMediaModeSnippets', () => {
  it('vision 使用 /chat/completions 与 image_url', () => {
    const snippet = buildMediaModeSnippets(BASE, KEY, MODEL, 'vision')
    expect(snippet.endpoint).toContain('/chat/completions')
    expect(snippet.curl).toContain('/chat/completions')
    expect(snippet.curl).toContain('image_url')
    expect(snippet.curl).toContain(MODEL)
    expect(snippet.ts).toContain('image_url')
    expect(snippet.py).toContain('image_url')
  })

  it('image_gen 使用 /images/generations', () => {
    const snippet = buildMediaModeSnippets(BASE, KEY, MODEL, 'image_gen')
    expect(snippet.endpoint).toContain('/images/generations')
    expect(snippet.curl).toContain('/images/generations')
    expect(snippet.curl).toContain('"prompt"')
    expect(snippet.curl).toContain('"size"')
    expect(snippet.ts).toContain('images.generate')
    expect(snippet.py).toContain('images.generate')
  })

  it('video_gen 使用 /videos 与可选 image', () => {
    const snippet = buildMediaModeSnippets(BASE, KEY, MODEL, 'video_gen')
    expect(snippet.endpoint).toContain('/videos')
    expect(snippet.curl).toContain('/videos')
    expect(snippet.curl).toContain('"image"')
    expect(snippet.ts).toContain('/videos')
    expect(snippet.py).toContain('/videos')
  })
})

describe('buildGuideSnippets chat', () => {
  it('对话模式 curl 使用 /chat/completions', () => {
    const snippets = buildGuideSnippets(BASE, KEY, MODEL)
    expect(snippets.openai.curl).toContain('/chat/completions')
    expect(snippets.openai.curlStream).toContain('stream')
    expect(snippets.anthropic.curl).toContain('/messages')
    expect(snippets.modelsCurlNote).toBeNull()
  })

  it('multi-grant vkey 的 modelsCurl 含前缀说明注释', () => {
    const snippets = buildGuideSnippets(BASE, KEY, MODEL, { multiGrantVkey: true })
    expect(snippets.modelsCurlNote).toContain('team-slug/name')
    expect(snippets.modelsCurlNote).toContain('个人')
    expect(snippets.modelsCurl).toContain('# multi-grant vkey')
  })
})
