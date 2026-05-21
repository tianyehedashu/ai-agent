/**
 * API 路径常量单测（ROOT_PATH / VITE_APP_ROOT 对齐）
 */

import { afterEach, describe, expect, it, vi } from 'vitest'

describe('api paths (default APP_ROOT)', () => {
  it('API_V1 与 gateway/openai 前缀', async () => {
    vi.stubEnv('VITE_APP_ROOT', '')
    vi.resetModules()
    const { API_V1, GATEWAY_API_BASE, GATEWAY_OPENAI_V1_BASE, GATEWAY_ANTHROPIC_BASE, apiV1Path } =
      await import('./paths')

    expect(API_V1).toBe('/api/v1')
    expect(GATEWAY_API_BASE).toBe('/api/v1/gateway')
    expect(GATEWAY_OPENAI_V1_BASE).toBe('/api/v1/openai/v1')
    expect(GATEWAY_ANTHROPIC_BASE).toBe('/api/v1/anthropic')
    expect(apiV1Path('/auth/me')).toBe('/api/v1/auth/me')
    expect(apiV1Path('listing-studio/jobs')).toBe('/api/v1/listing-studio/jobs')
  })
})

describe('api paths (VITE_APP_ROOT=/ai-agent)', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it('带服务级前缀的路径拼接', async () => {
    vi.stubEnv('VITE_APP_ROOT', '/ai-agent')
    vi.resetModules()
    const { API_V1, GATEWAY_OPENAI_V1_BASE, apiV1Path } = await import('./paths')

    expect(API_V1).toBe('/ai-agent/api/v1')
    expect(GATEWAY_OPENAI_V1_BASE).toBe('/ai-agent/api/v1/openai/v1')
    expect(apiV1Path('/gateway/models/available')).toBe('/ai-agent/api/v1/gateway/models/available')
  })

  it('去除尾斜杠', async () => {
    vi.stubEnv('VITE_APP_ROOT', '/ai-agent/')
    vi.resetModules()
    const { API_V1 } = await import('./paths')
    expect(API_V1).toBe('/ai-agent/api/v1')
  })
})
