import { describe, expect, it } from 'vitest'

import type { CredentialSummary } from '@/api/gateway'

import { credentialSummaryLabel } from './credential-summary-display'

const teamSummary: CredentialSummary = {
  id: 'cred-team',
  provider: 'openai',
  name: 'Team OpenAI',
  scope: 'team',
  is_active: true,
  is_config_managed: false,
}

describe('credentialSummaryLabel', () => {
  it('uses summary name when present', () => {
    expect(credentialSummaryLabel(teamSummary, teamSummary.id)).toBe('Team OpenAI')
  })

  it('falls back to short id when summary missing', () => {
    expect(credentialSummaryLabel(undefined, '12345678-abcd-efgh')).toBe('未知凭据 (12345678…)')
  })
})
