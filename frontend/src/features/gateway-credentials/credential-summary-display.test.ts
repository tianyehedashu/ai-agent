import { describe, expect, it } from 'vitest'

import type { CredentialSummary } from '@/api/gateway'

import { canLinkToCredentialDetail, credentialSummaryLabel } from './credential-summary-display'

const teamSummary: CredentialSummary = {
  id: 'cred-team',
  provider: 'openai',
  name: 'Team OpenAI',
  scope: 'team',
  is_active: true,
  is_config_managed: false,
}

const systemSummary: CredentialSummary = {
  id: 'cred-sys',
  provider: 'openai',
  name: 'Platform OpenAI',
  scope: 'system',
  is_active: true,
  is_config_managed: true,
}

describe('credentialSummaryLabel', () => {
  it('uses summary name when present', () => {
    expect(credentialSummaryLabel(teamSummary, teamSummary.id)).toBe('Team OpenAI')
  })

  it('falls back to short id when summary missing', () => {
    expect(credentialSummaryLabel(undefined, '12345678-abcd-efgh')).toBe('未知凭据 (12345678…)')
  })
})

describe('canLinkToCredentialDetail', () => {
  it('allows team admin on team credential', () => {
    expect(canLinkToCredentialDetail(teamSummary, true, false)).toBe(true)
  })

  it('blocks member without admin', () => {
    expect(canLinkToCredentialDetail(teamSummary, false, false)).toBe(false)
  })

  it('blocks non-platform admin on system credential', () => {
    expect(canLinkToCredentialDetail(systemSummary, true, false)).toBe(false)
  })

  it('allows platform admin on system credential', () => {
    expect(canLinkToCredentialDetail(systemSummary, true, true)).toBe(true)
  })
})
