/**
 * 模型列表「按凭据筛选」选项构建与合并。
 */

import type { GatewayModel } from '@/api/gateway'
import {
  formatGatewayModelCredentialFilterLabel,
  type GatewayModelCredentialFilterOption,
} from '@/features/gateway-models/gateway-model-credential-filter-select'

const UUID_FRAGMENT = /^[0-9a-f]{8}$/i

function looksLikeUuidFragment(name: string): boolean {
  return UUID_FRAGMENT.test(name.trim())
}

/** 从当前页模型行提取可筛选凭据（必须有 credential_name，避免 trigger 显示 UUID 片段） */
export function credentialFilterOptionsFromModels(
  models: readonly GatewayModel[],
  teamNameById: ReadonlyMap<string, string>
): GatewayModelCredentialFilterOption[] {
  const byId = new Map<string, GatewayModelCredentialFilterOption>()
  for (const model of models) {
    const displayName = model.credential_name?.trim()
    if (!model.credential_id || !displayName) continue
    if (byId.has(model.credential_id)) continue
    const teamId = model.tenant_id ?? model.team_id
    byId.set(model.credential_id, {
      id: model.credential_id,
      name: displayName,
      provider: model.provider,
      teamLabel: teamId ? teamNameById.get(teamId) : undefined,
    })
  }
  return Array.from(byId.values())
}

/**
 * 合并 summaries 与模型行凭据名：列表上的 credential_name 优先（成员可见名），summaries 补全通道/团队标签。
 */
export function mergeCredentialFilterOptions(
  fromSummaries: readonly GatewayModelCredentialFilterOption[],
  fromModels: readonly GatewayModelCredentialFilterOption[]
): GatewayModelCredentialFilterOption[] {
  const byId = new Map<string, GatewayModelCredentialFilterOption>()

  for (const option of fromModels) {
    byId.set(option.id, option)
  }

  for (const option of fromSummaries) {
    const existing = byId.get(option.id)
    if (!existing) {
      byId.set(option.id, option)
      continue
    }
    const preferSummaryName =
      looksLikeUuidFragment(existing.name) ||
      (existing.name.length < option.name.length && option.name.length > 0)
    byId.set(option.id, {
      id: option.id,
      name: preferSummaryName ? option.name : existing.name,
      provider: option.provider ?? existing.provider,
      teamLabel: existing.teamLabel ?? option.teamLabel,
    })
  }

  return Array.from(byId.values()).sort((a, b) =>
    formatGatewayModelCredentialFilterLabel(a).localeCompare(
      formatGatewayModelCredentialFilterLabel(b),
      'zh-CN'
    )
  )
}
