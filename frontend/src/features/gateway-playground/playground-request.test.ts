import { describe, expect, test } from 'vitest'

import {
  buildImageGenRequestBody,
  buildPlaygroundRequestBody,
  buildVideoGenRequestBody,
  buildVisionRequestBody,
  maskAuthHeadersForDisplay,
  maskTokenForDisplay,
} from './playground-request'

describe('buildPlaygroundRequestBody', () => {
  test('OpenAI 风格包含 user message', () => {
    const body = buildPlaygroundRequestBody({
      model: 'deepseek-chat',
      prompt: '用一句话介绍你自己。',
      stream: true,
      flavor: 'openai',
    })
    expect(body).toEqual({
      model: 'deepseek-chat',
      stream: true,
      messages: [{ role: 'user', content: '用一句话介绍你自己。' }],
    })
  })

  test('Anthropic 风格包含 max_tokens', () => {
    const body = buildPlaygroundRequestBody({
      model: 'claude',
      prompt: 'hi',
      stream: false,
      flavor: 'anthropic',
      maxTokens: 512,
    })
    expect(body.max_tokens).toBe(512)
    expect(body.messages).toEqual([{ role: 'user', content: 'hi' }])
  })
})

describe('buildVisionRequestBody', () => {
  test('多模态 content 含 image_url', () => {
    const body = buildVisionRequestBody({
      model: 'gpt-4o',
      prompt: '描述图片',
      imageUrl: 'https://example.com/a.png',
      stream: false,
    })
    const messages = body.messages as { role: string; content: unknown[] }[]
    expect(messages[0]?.content).toEqual(
      expect.arrayContaining([
        { type: 'text', text: '描述图片' },
        { type: 'image_url', image_url: { url: 'https://example.com/a.png' } },
      ])
    )
  })
})

describe('buildImageGenRequestBody', () => {
  test('包含 prompt 与 size', () => {
    const body = buildImageGenRequestBody({
      model: 'dall-e-3',
      prompt: 'a cat',
      size: '1024x1024',
      n: 2,
    })
    expect(body).toMatchObject({ model: 'dall-e-3', prompt: 'a cat', size: '1024x1024', n: 2 })
  })
})

describe('buildVideoGenRequestBody', () => {
  test('可选 image 图生视频', () => {
    const body = buildVideoGenRequestBody({
      model: 'seedance',
      prompt: '跳舞',
      imageUrl: 'https://example.com/ref.png',
    })
    expect(body.image).toBe('https://example.com/ref.png')
  })
})

describe('maskAuthHeadersForDisplay', () => {
  test('脱敏 Bearer 与 x-api-key', () => {
    const masked = maskAuthHeadersForDisplay({
      Authorization: 'Bearer sk-gw-abcdefghijklmnop',
      'x-api-key': 'sk-gw-abcdefghijklmnop',
      'Content-Type': 'application/json',
    })
    expect(masked.Authorization).toBe('Bearer sk-gw-ab...***')
    expect(masked['x-api-key']).toBe('sk-gw-ab...***')
    expect(masked['Content-Type']).toBe('application/json')
  })
})

describe('maskTokenForDisplay', () => {
  test('短 token 返回 ***', () => {
    expect(maskTokenForDisplay('short')).toBe('***')
  })
})
