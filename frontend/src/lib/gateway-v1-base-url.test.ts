/**
 * Gateway OpenAI/Anthropic base URL 解析单测
 */

import { afterEach, describe, expect, it, vi } from 'vitest'

describe('resolveGatewayV1BaseUrl', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it('DEV 环境默认指向 localhost OpenAI 兼容面', async () => {
    vi.stubEnv('VITE_APP_ROOT', '')
    vi.stubEnv('VITE_API_URL', '')
    vi.stubEnv('DEV', 'true')
    vi.resetModules()
    const { resolveGatewayV1BaseUrl } = await import('./gateway-v1-base-url')
    expect(resolveGatewayV1BaseUrl()).toBe('http://localhost:8000/api/v1/openai/v1')
  })

  it('VITE_API_URL 为 origin 时拼接 OpenAI 兼容路径', async () => {
    vi.stubEnv('VITE_APP_ROOT', '')
    vi.stubEnv('VITE_API_URL', 'https://api.example.com')
    vi.stubEnv('DEV', '')
    vi.resetModules()
    const { resolveGatewayV1BaseUrl } = await import('./gateway-v1-base-url')
    expect(resolveGatewayV1BaseUrl()).toBe('https://api.example.com/api/v1/openai/v1')
  })

  it('VITE_APP_ROOT 与 VITE_API_URL 同时配置', async () => {
    vi.stubEnv('VITE_APP_ROOT', '/ai-agent')
    vi.stubEnv('VITE_API_URL', 'https://api.example.com')
    vi.stubEnv('DEV', '')
    vi.resetModules()
    const { resolveGatewayV1BaseUrl, resolveGatewayAnthropicBaseUrl } =
      await import('./gateway-v1-base-url')
    expect(resolveGatewayV1BaseUrl()).toBe('https://api.example.com/ai-agent/api/v1/openai/v1')
    expect(resolveGatewayAnthropicBaseUrl()).toBe(
      'https://api.example.com/ai-agent/api/v1/anthropic'
    )
  })
})
