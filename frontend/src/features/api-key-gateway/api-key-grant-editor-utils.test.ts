import { describe, expect, it } from 'vitest'

import { gatewayGrantsToDrafts, grantsToRequests } from './api-key-grant-editor-utils'

import type { GrantDraft } from './api-key-grant-editor'

describe('api-key-grant-editor-utils', () => {
  it('grantsToRequests 映射 draft 为 API 请求体', () => {
    const draft: GrantDraft = {
      localId: 'local-1',
      team_id: 'team-a',
      allowed_models: ['gpt-4'],
      allowed_capabilities: ['chat'],
      rpm_limit: 100,
      tpm_limit: 200,
      store_full_messages: true,
      guardrail_enabled: false,
    }

    expect(grantsToRequests([draft])).toEqual([
      {
        team_id: 'team-a',
        allowed_models: ['gpt-4'],
        allowed_capabilities: ['chat'],
        rpm_limit: 100,
        tpm_limit: 200,
        store_full_messages: true,
        guardrail_enabled: false,
      },
    ])
  })

  it('gatewayGrantsToDrafts 生成带 localId 的 draft', () => {
    const drafts = gatewayGrantsToDrafts([
      {
        team_id: 'team-b',
        allowed_models: [],
        allowed_capabilities: ['image_gen'],
        rpm_limit: null,
        tpm_limit: null,
        store_full_messages: false,
        guardrail_enabled: true,
      },
    ])

    expect(drafts).toHaveLength(1)
    expect(drafts[0]?.team_id).toBe('team-b')
    expect(drafts[0]?.allowed_capabilities).toEqual(['image_gen'])
    expect(drafts[0]?.localId).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
    )
  })
})
