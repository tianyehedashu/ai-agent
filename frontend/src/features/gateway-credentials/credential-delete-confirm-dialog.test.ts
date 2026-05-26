import { describe, expect, test } from 'vitest'

import type { ProviderCredential } from '@/api/gateway'

import { credentialDeleteDescription } from './credential-delete-descriptions'

function cred(overrides: Partial<ProviderCredential> = {}): ProviderCredential {
  return {
    id: 'c1',
    tenant_id: 't1',
    scope: 'team',
    scope_id: null,
    provider: 'openai',
    name: 'My Key',
    api_base: null,
    is_active: true,
    extra: null,
    created_at: '2026-01-01T00:00:00Z',
    api_key_masked: 'sk-…xxxx',
    ...overrides,
  }
}

describe('credentialDeleteDescription', () => {
  test('personal 变体文案', () => {
    expect(credentialDeleteDescription(cred({ scope: 'user' }), 'personal')).toContain(
      '个人注册模型'
    )
  })

  test('managed 普通凭据', () => {
    expect(credentialDeleteDescription(cred())).toContain('虚拟 Key')
  })

  test('managed 配置同步 system 凭据', () => {
    expect(
      credentialDeleteDescription(cred({ scope: 'system', is_config_managed: true }), 'managed')
    ).toContain('配置同步凭据')
  })
})
