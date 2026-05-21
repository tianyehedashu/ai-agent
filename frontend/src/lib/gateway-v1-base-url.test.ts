/**
 * Gateway OpenAI/Anthropic base URL 解析单测
 */

import { afterEach, describe, expect, it, vi } from 'vitest'

describe('resolveGatewayV1BaseUrl', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it('未配置 VITE_API_URL 时使用当前 origin + OpenAI 兼容路径（经 Vite 代理）', async () => {
    vi.unstubAllEnvs()
    vi.resetModules()
    const { resolveGatewayV1BaseUrl } = await import('./gateway-v1-base-url')
    expect(resolveGatewayV1BaseUrl()).toBe(`${window.location.origin}/ai-agent/api/v1/openai/v1`)
  })

  it('VITE_API_URL 为 origin 时拼接 OpenAI 兼容路径', async () => {
    vi.stubEnv('VITE_APP_ROOT', '/ai-agent')
    vi.stubEnv('VITE_API_URL', 'https://api.example.com')
    vi.resetModules()
    const { resolveGatewayV1BaseUrl } = await import('./gateway-v1-base-url')
    expect(resolveGatewayV1BaseUrl()).toBe('https://api.example.com/ai-agent/api/v1/openai/v1')
  })

  it('VITE_APP_ROOT 与 VITE_API_URL 同时配置', async () => {
    vi.stubEnv('VITE_APP_ROOT', '/ai-agent')
    vi.stubEnv('VITE_API_URL', 'https://api.example.com')
    vi.resetModules()
    const { resolveGatewayV1BaseUrl, resolveGatewayAnthropicBaseUrl } =
      await import('./gateway-v1-base-url')
    expect(resolveGatewayV1BaseUrl()).toBe('https://api.example.com/ai-agent/api/v1/openai/v1')
    expect(resolveGatewayAnthropicBaseUrl()).toBe(
      'https://api.example.com/ai-agent/api/v1/anthropic'
    )
  })
})
