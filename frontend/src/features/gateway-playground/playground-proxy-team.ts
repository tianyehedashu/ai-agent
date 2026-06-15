/**
 * Playground 代理调用团队上下文：与后端 vkey.team_id 解析对齐。
 */

import type { VirtualKey } from '@/api/gateway'
import type { VirtualKeyTeamGrant } from '@/api/gateway/grants'
import type { GatewayTeam } from '@/stores/gateway-team'

import {
  resolvePlaygroundContextTeamId,
  type PlaygroundCredentialOption,
} from './playground-credential-options'

import type { ModelCandidate } from './playground-mode-filter'

const PRIMARY_TEAM_GROUP_KEY = '__primary__'

export interface PlaygroundTeamModelGroup {
  groupKey: string
  label: string
  models: ModelCandidate[]
}

function grantGroupLabel(grants: readonly VirtualKeyTeamGrant[], teamSlug: string | null): string {
  if (teamSlug === null) {
    const self = grants.find((g) => g.is_self)
    if (self?.granted_team_name) return `${self.granted_team_name} · 个人`
    return '个人'
  }
  const grant = grants.find((g) => g.granted_team_slug === teamSlug)
  if (grant?.granted_team_name) return `${grant.granted_team_name} (${teamSlug})`
  return teamSlug
}

function resolveModelTeamGroupKey(model: ModelCandidate): string {
  if (model.teamSlug !== undefined && model.teamSlug !== null && model.teamSlug !== '')
    return model.teamSlug
  const slash = model.name.indexOf('/')
  if (slash > 0) return model.name.slice(0, slash)
  return PRIMARY_TEAM_GROUP_KEY
}

/** multi-grant vkey 代理模型列表按工作区分组（个人/主属 team 优先） */
export function buildMultiGrantTeamModelGroups(
  candidates: readonly ModelCandidate[],
  grants: readonly VirtualKeyTeamGrant[]
): PlaygroundTeamModelGroup[] | undefined {
  if (candidates.length === 0 || grants.length <= 1) return undefined
  if (!candidates.some((m) => resolveModelTeamGroupKey(m) !== PRIMARY_TEAM_GROUP_KEY)) {
    return undefined
  }

  const buckets = new Map<string, ModelCandidate[]>()
  for (const model of candidates) {
    const key = resolveModelTeamGroupKey(model)
    const bucket = buckets.get(key) ?? []
    bucket.push(model)
    buckets.set(key, bucket)
  }

  const orderedKeys: string[] = []
  if (buckets.has(PRIMARY_TEAM_GROUP_KEY)) {
    orderedKeys.push(PRIMARY_TEAM_GROUP_KEY)
  }
  for (const grant of grants) {
    if (grant.is_self) continue
    const slug = grant.granted_team_slug
    if (slug && buckets.has(slug) && !orderedKeys.includes(slug)) {
      orderedKeys.push(slug)
    }
  }
  for (const key of buckets.keys()) {
    if (!orderedKeys.includes(key)) orderedKeys.push(key)
  }

  return orderedKeys.map((key) => ({
    groupKey: key,
    label: grantGroupLabel(grants, key === PRIMARY_TEAM_GROUP_KEY ? null : key),
    models: [...(buckets.get(key) ?? [])].sort((a, b) => a.name.localeCompare(b.name)),
  }))
}

export function isPersonalGatewayTeam(team: Pick<GatewayTeam, 'kind'> | null | undefined): boolean {
  return team?.kind === 'personal'
}

/**
 * 下拉分组（与 Key 绑定团队对齐）：
 * - 个人工作区 Key → 模型归入 personal 分组（与协作团队 Key 的「团队模型」对称）
 * - 协作团队 Key → 仅「团队模型」，不含 BYOK 个人模型
 */
export function splitPlaygroundModelCandidatesForDisplay(
  models: readonly ModelCandidate[],
  isPersonalProxyTeam: boolean
): { teamCandidates: ModelCandidate[]; personalCandidates: ModelCandidate[] } {
  const teamCandidates: ModelCandidate[] = []
  const personalCandidates: ModelCandidate[] = []
  for (const m of models) {
    if (isPersonalProxyTeam) {
      personalCandidates.push(m)
      continue
    }
    if (m.scope === 'team') {
      teamCandidates.push(m)
    }
  }
  return { teamCandidates, personalCandidates }
}

/** 实际代理解析使用的团队：已选 Key 优先，否则凭据/工作区上下文。 */
export function resolvePlaygroundProxyTeamId(
  selectedKey: Pick<VirtualKey, 'team_id'> | null | undefined,
  credentialId: string,
  credentialById: ReadonlyMap<string, PlaygroundCredentialOption>,
  workspaceTeamId: string | null
): string | null {
  if (selectedKey?.team_id) return selectedKey.team_id
  return resolvePlaygroundContextTeamId(credentialId, credentialById, workspaceTeamId)
}

/** multi-grant 列表 id（team-slug/name）与 allowed_models（注册名）对齐 */
export function virtualKeyAllowsModelName(
  modelName: string,
  allowedModels: readonly string[] | undefined
): boolean {
  if (!allowedModels || allowedModels.length === 0) return true
  const allowed = new Set(allowedModels)
  if (allowed.has(modelName)) return true
  const slash = modelName.lastIndexOf('/')
  if (slash >= 0 && allowed.has(modelName.slice(slash + 1))) return true
  return false
}

/** Key 白名单过滤（模型名 / 虚拟路由名）；空列表表示不限制。 */
export function filterPlaygroundNamesForVirtualKey<T extends { name: string }>(
  items: readonly T[],
  allowedModels: readonly string[] | undefined
): T[] {
  if (!allowedModels || allowedModels.length === 0) return [...items]
  return items.filter((item) => virtualKeyAllowsModelName(item.name, allowedModels))
}

export function filterPlaygroundCandidatesForVirtualKey(
  candidates: readonly ModelCandidate[],
  allowedModels: readonly string[] | undefined
): ModelCandidate[] {
  return filterPlaygroundNamesForVirtualKey(candidates, allowedModels)
}
