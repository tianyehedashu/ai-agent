/**
 * 凭据相关常量与小工具。
 *
 * 凭据 provider 列表与差异化字段的单一事实源现在迁移到
 * [`provider-schemas.ts`](./provider-schemas.ts) —— 用户/团队/系统凭据
 * 共用同一份 schema，按 `availableScopes` 派生不同 scope 下的下拉项。
 */

import { providerLabel, providersForScope, type CredentialFormScope } from './provider-schemas'

/** 与后端 `CONFIG_MANAGED_*` 一致 */
export const CONFIG_MANAGED_CREDENTIAL_NAME = 'app-config-default'
export const CONFIG_MANAGED_BY = 'config'

/** 个人 Tab 渲染所需 provider 顺序（按 schema 表派生，保留对外稳定 API） */
export const USER_GATEWAY_CREDENTIAL_PROVIDER_IDS: readonly string[] = providersForScope(
  'user'
).map((s) => s.id)

export function credentialProviderLabel(id: string): string {
  return providerLabel(id)
}

export function credentialProviderIdsForScope(scope: CredentialFormScope): readonly string[] {
  return providersForScope(scope).map((s) => s.id)
}
