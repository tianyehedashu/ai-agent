/**
 * 调用统计页筛选下拉的数据源（团队工作区 vs 跨团队/全平台）。
 */

import type { PlatformUserSummary } from '@/api/adminUsers'
import type { VirtualKey } from '@/api/gateway/keys'
import type { GatewayUsageAggregation } from '@/api/gateway/logs'
import type { GatewayModel } from '@/api/gateway/models'
import type { TeamMember } from '@/api/gateway/teams'
import type { GatewayFilterOption } from '@/features/gateway-usage/gateway-filter-combobox'

export function usageStatsShowMemberFilter(aggregation: GatewayUsageAggregation): boolean {
  return aggregation !== 'user'
}

export type StatsFilterModelRef = Pick<GatewayModel, 'name' | 'real_model' | 'provider'>

export function modelOptionValuesFromModels(models: readonly StatsFilterModelRef[]): string[] {
  const values: string[] = []
  for (const model of models) {
    values.push(model.name)
    values.push(model.real_model)
  }
  return values
}

/** 统计页模型筛：完整展示 name / real_model，避免单行截断后无法区分。 */
export function modelFilterOptionsForStats(
  models: readonly StatsFilterModelRef[]
): GatewayFilterOption[] {
  const seen = new Set<string>()
  const options: GatewayFilterOption[] = []

  const push = (value: string, label: string, meta?: string): void => {
    const trimmed = value.trim()
    if (trimmed.length === 0 || seen.has(trimmed)) return
    seen.add(trimmed)
    options.push({ value: trimmed, label, meta })
  }

  for (const model of models) {
    const name = model.name.trim()
    const realModel = model.real_model.trim()
    if (name.length > 0) {
      push(name, name, realModel.length > 0 && realModel !== name ? realModel : model.provider)
    }
    if (realModel.length > 0 && realModel !== name) {
      push(realModel, realModel, name.length > 0 ? name : model.provider)
    }
  }

  return options.sort((a, b) => a.label.localeCompare(b.label))
}

function uniqueSorted(values: string[]): GatewayFilterOption[] {
  return Array.from(new Set(values.filter((v) => v.trim().length > 0)))
    .sort((a, b) => a.localeCompare(b))
    .map((value) => ({ value, label: value }))
}

export interface StatsFilterCredentialRef {
  id: string
  name: string
  provider: string
}

export function credentialFilterOptions(
  credentials: readonly StatsFilterCredentialRef[]
): GatewayFilterOption[] {
  return credentials.map((credential) => ({
    value: credential.id,
    label: credential.name,
    meta: credential.provider,
  }))
}

export function memberFilterOptionsFromTeamMembers(
  members: readonly TeamMember[]
): GatewayFilterOption[] {
  return members.map((member) => ({
    value: member.user_id,
    label: member.user_name ?? member.user_email ?? member.user_id,
    meta: member.role,
  }))
}

export function memberFilterOptionsFromPlatformUsers(
  users: readonly PlatformUserSummary[]
): GatewayFilterOption[] {
  return users.map((user) => ({
    value: user.id,
    label: user.name ?? user.email,
    meta: user.email,
  }))
}

export function keyFilterOptions(keys: readonly VirtualKey[]): GatewayFilterOption[] {
  return keys.map((key) => ({
    value: key.id,
    label: key.name,
    meta: key.masked_key,
  }))
}

/** 凭据 + 模型注册表中的 provider（不含仅出现在调用日志里的项）。 */
export function registryProviderFilterOptions(
  credentials: readonly { provider: string }[],
  models: readonly { provider: string }[]
): GatewayFilterOption[] {
  const values = [...credentials.map((c) => c.provider), ...models.map((m) => m.provider)]
  return uniqueSorted(values)
}

export function providerFilterOptionsFromUsageItems(
  items: readonly { group_key: string; label: string }[]
): GatewayFilterOption[] {
  const options: GatewayFilterOption[] = []
  const seen = new Set<string>()
  for (const item of items) {
    const value = item.group_key.trim()
    if (value.length === 0 || seen.has(value)) continue
    seen.add(value)
    const label = item.label.trim() || value
    options.push({ value, label })
  }
  return options.sort((a, b) => a.label.localeCompare(b.label))
}

export function providerFilterOptionsFromProfiles(
  profiles: readonly { provider: string; label: string }[]
): GatewayFilterOption[] {
  const byProvider = new Map<string, string>()
  for (const profile of profiles) {
    const value = profile.provider.trim()
    if (value.length === 0) continue
    const key = value.toLowerCase()
    if (!byProvider.has(key)) {
      byProvider.set(key, profile.label.trim() || value)
    }
  }
  return Array.from(byProvider.entries())
    .sort((a, b) => a[1].localeCompare(b[1]))
    .map(([value, label]) => ({ value, label }))
}

/** 合并多路 provider 来源；usage 项优先保留 group_key（与统计 API 一致）。 */
export function mergeProviderFilterOptions(
  ...sources: readonly (readonly GatewayFilterOption[])[]
): GatewayFilterOption[] {
  const byValue = new Map<string, GatewayFilterOption>()
  for (const list of sources) {
    for (const option of list) {
      const value = option.value.trim()
      if (value.length === 0) continue
      if (!byValue.has(value)) {
        byValue.set(value, { value, label: option.label.trim() || value, meta: option.meta })
      }
    }
  }
  return Array.from(byValue.values()).sort((a, b) => a.label.localeCompare(b.label))
}
