import { describe, expect, it } from 'vitest'

import {
  inviteCandidateScopeLabel,
  parseInviteCandidateScope,
} from '@/features/gateway-teams/team-invite-candidate-scope'

describe('parseInviteCandidateScope', () => {
  it('defaults to all_users', () => {
    expect(parseInviteCandidateScope(null)).toBe('all_users')
    expect(parseInviteCandidateScope(undefined)).toBe('all_users')
  })

  it('reads shared_teams from settings', () => {
    expect(parseInviteCandidateScope({ invite_candidate_scope: 'shared_teams' })).toBe(
      'shared_teams'
    )
  })
})

describe('inviteCandidateScopeLabel', () => {
  it('returns Chinese labels', () => {
    expect(inviteCandidateScopeLabel('all_users')).toBe('全站注册用户')
    expect(inviteCandidateScopeLabel('shared_teams')).toBe('仅共同团队网络')
  })
})
