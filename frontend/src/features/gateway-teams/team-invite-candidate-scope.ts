import type { InviteCandidateScope } from '@/api/gateway/teams'

export const INVITE_CANDIDATE_SCOPE_SETTINGS_KEY = 'invite_candidate_scope'

export function parseInviteCandidateScope(
  settings: Record<string, unknown> | null | undefined
): InviteCandidateScope {
  const raw = settings?.[INVITE_CANDIDATE_SCOPE_SETTINGS_KEY]
  return raw === 'shared_teams' ? 'shared_teams' : 'all_users'
}

export function inviteCandidateScopeLabel(scope: InviteCandidateScope): string {
  return scope === 'shared_teams' ? '仅共同团队网络' : '全站注册用户'
}
