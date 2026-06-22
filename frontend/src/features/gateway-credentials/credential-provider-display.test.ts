import { describe, expect, it } from 'vitest'

import { credentialProviderLabel } from './credential-provider-display'

describe('credentialProviderLabel', () => {
  it('prefers created_by_label from API', () => {
    expect(
      credentialProviderLabel({
        created_by_label: 'denglietao@qq.com',
        scope: 'team',
        is_config_managed: false,
      })
    ).toBe('denglietao@qq.com')
  })

  it('falls back for system credentials', () => {
    expect(
      credentialProviderLabel({
        scope: 'system',
        is_config_managed: true,
      })
    ).toBe('平台（配置同步）')
  })

  it('falls back for personal credentials', () => {
    expect(
      credentialProviderLabel({
        scope: 'user',
        is_config_managed: false,
      })
    ).toBe('个人')
  })
})
