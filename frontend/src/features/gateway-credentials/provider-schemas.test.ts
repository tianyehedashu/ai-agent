/**
 * @see provider-schemas.ts
 */

import { describe, expect, it } from 'vitest'

import {
  PROVIDER_SCHEMAS,
  apiKeyLabelForProvider,
  defaultApiBaseForProvider,
  extraFieldsForProvider,
  getProviderSchema,
  providerLabel,
  providersForScope,
} from './provider-schemas'

describe('provider-schemas', () => {
  it('exposes core providers with stable ids', () => {
    const ids = PROVIDER_SCHEMAS.map((s) => s.id)
    for (const required of [
      'openai',
      'anthropic',
      'azure',
      'bedrock',
      'vertex_ai',
      'gemini',
      'dashscope',
      'deepseek',
      'volcengine',
      'zhipuai',
    ]) {
      expect(ids).toContain(required)
    }
  })

  it('limits user scope to BYOK-friendly providers', () => {
    const userProviders = providersForScope('user').map((s) => s.id)
    expect(new Set(userProviders)).toEqual(
      new Set([
        'openai',
        'anthropic',
        'dashscope',
        'zhipuai',
        'deepseek',
        'moonshot',
        'volcengine',
        'agnes',
      ])
    )
  })

  it('exposes the wider managed catalog for team/system scope', () => {
    const teamProviders = providersForScope('team').map((s) => s.id)
    for (const required of ['openai', 'azure', 'bedrock', 'vertex_ai', 'gemini', 'cohere']) {
      expect(teamProviders).toContain(required)
    }
    expect(teamProviders).not.toContain('non-existent-provider')
  })

  it('returns matching defaults for popular providers', () => {
    expect(defaultApiBaseForProvider('openai')).toBe('https://api.openai.com/v1')
    expect(defaultApiBaseForProvider('deepseek')).toBe('https://api.deepseek.com/v1')
    expect(defaultApiBaseForProvider('volcengine')).toBe('https://ark.cn-beijing.volces.com/api/v3')
    expect(defaultApiBaseForProvider('cohere')).toBe('')
  })

  it('returns empty string for unknown provider default api_base', () => {
    expect(defaultApiBaseForProvider('non-existent-provider')).toBe('')
  })

  it('renames api_key label for bedrock', () => {
    expect(apiKeyLabelForProvider('bedrock')).toBe('AWS Access Key ID')
    expect(apiKeyLabelForProvider('openai')).toBe('API Key')
  })

  it('returns provider-specific extra fields with keys aligned to backend whitelist', () => {
    const azureKeys = extraFieldsForProvider('azure').map((f) => f.key)
    expect(azureKeys).toContain('api_version')

    const bedrockKeys = extraFieldsForProvider('bedrock').map((f) => f.key)
    expect(bedrockKeys).toEqual(
      expect.arrayContaining(['aws_secret_access_key', 'aws_region_name', 'aws_session_token'])
    )

    const vertexKeys = extraFieldsForProvider('vertex_ai').map((f) => f.key)
    expect(vertexKeys).toEqual(
      expect.arrayContaining(['vertex_project', 'vertex_location', 'vertex_credentials'])
    )

    const volcKeys = extraFieldsForProvider('volcengine').map((f) => f.key)
    expect(volcKeys).toEqual(expect.arrayContaining(['region', 'endpoint_id', 'image_endpoint_id']))

    expect(extraFieldsForProvider('deepseek')).toHaveLength(0)
  })

  it('marks dashscope/zhipuai/volcengine as api_base required', () => {
    expect(getProviderSchema('dashscope')?.apiBaseRequired).toBe(true)
    expect(getProviderSchema('zhipuai')?.apiBaseRequired).toBe(true)
    expect(getProviderSchema('volcengine')?.apiBaseRequired).toBe(true)
    expect(getProviderSchema('openai')?.apiBaseRequired).toBeFalsy()
  })

  it('falls back to raw id when no label is registered', () => {
    expect(providerLabel('volcengine')).toBe('火山引擎 (豆包/方舟)')
    expect(providerLabel('non-existent-provider')).toBe('non-existent-provider')
  })
})
