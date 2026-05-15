/**
 * 与后端 `domains.gateway.domain.types.USER_GATEWAY_CREDENTIAL_PROVIDERS` 一致（用户 /my-credentials）。
 * 团队凭据创建支持更广的 provider 集合（与网关管理路由一致）。
 */

import { PROVIDER_LABELS } from '@/types/provider-config'

/** 用户私有凭据支持的 provider id（顺序稳定，供 UI 遍历） */
export const USER_GATEWAY_CREDENTIAL_PROVIDER_IDS: readonly string[] = [
  'anthropic',
  'dashscope',
  'deepseek',
  'openai',
  'volcengine',
  'zhipuai',
]

/** 团队/系统凭据创建下拉（管理面） */
export const TEAM_MANAGED_CREDENTIAL_PROVIDER_IDS: readonly string[] = [
  'openai',
  'anthropic',
  'azure',
  'dashscope',
  'deepseek',
  'volcengine',
  'zhipuai',
  'gemini',
  'cohere',
  'mistral',
  'fireworks',
  'together_ai',
]

export function credentialProviderLabel(id: string): string {
  return PROVIDER_LABELS[id] ?? id
}
