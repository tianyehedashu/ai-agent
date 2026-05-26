import type { ProviderCredential } from '@/api/gateway/credentials'
import { isConfigManagedSystemCredential } from '@/features/gateway-credentials/config-managed-credential'

export type CredentialDeleteVariant = 'managed' | 'personal'

export function credentialDeleteDescription(
  credential: ProviderCredential,
  variant: CredentialDeleteVariant = 'managed'
): string {
  if (variant === 'personal') {
    return `确定删除「${credential.name}」？将同时删除所有引用该凭据的个人注册模型，并更新虚拟 Key / 路由中的模型白名单。`
  }
  if (isConfigManagedSystemCredential(credential)) {
    return `确定删除「${credential.name}」？将同时删除所有引用该凭据的注册模型；此为配置同步凭据，下次从配置重载或重启后可能自动恢复。`
  }
  return `确定删除「${credential.name}」？将同时删除所有引用该凭据的注册模型，并更新虚拟 Key / 路由中的模型白名单。`
}
