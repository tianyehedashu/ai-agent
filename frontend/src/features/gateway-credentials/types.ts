/** 凭据上游探测 / 批量导入的作用域（个人 / 团队 / 系统） */
export type CredentialUpstreamScope = 'team' | 'user' | 'system'

/** 个人 BYOK 凭据走 `/my-credentials`；团队与系统凭据走团队管理 API。 */
export function isPersonalUpstreamScope(scope: CredentialUpstreamScope): boolean {
  return scope === 'user'
}

/** 团队/系统管理面凭据的上游作用域（个人凭据不在此列）。 */
export function managedCredentialUpstreamScope(
  credScope: 'team' | 'system' | 'user' | null
): CredentialUpstreamScope {
  return credScope === 'system' ? 'system' : 'team'
}
