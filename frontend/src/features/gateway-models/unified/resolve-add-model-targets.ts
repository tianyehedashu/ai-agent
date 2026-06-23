/**
 * 统一模型列表「添加模型」入口：按归属筛选与权限解析可跳转目标。
 */

import { personalModelsRegisterHref, teamModelsRegisterHref } from '@/features/gateway-models/paths'

import type { UnifiedModelScopeFilter } from './unified-models-filters'

export type AddModelTargetScope = 'personal' | 'team' | 'system'

export interface AddModelTarget {
  scope: AddModelTargetScope
  label: string
  href: string
}

const ADD_MODEL_LABELS: Record<AddModelTargetScope, string> = {
  personal: '添加个人模型',
  team: '添加团队模型',
  system: '添加系统模型',
}

export interface ResolveAddModelTargetsInput {
  scopeFilter: UnifiedModelScopeFilter
  routeTeamId: string
  credentialId?: string
  /** URL affiliationTeamId；须在 eligibleTeamIds 中才优先使用 */
  affiliationTeamId?: string
  canRegisterTeam: boolean
  isPlatformAdmin: boolean
  /** 可注册团队的候选 ID（writable + member） */
  eligibleTeamIds: ReadonlySet<string>
  /** 默认团队：writableTeams[0] ?? memberTeams[0] */
  defaultRegisterTeamId?: string
}

function resolveRegisterTeamId(input: ResolveAddModelTargetsInput): string | undefined {
  const { affiliationTeamId, eligibleTeamIds, defaultRegisterTeamId } = input
  if (affiliationTeamId && affiliationTeamId !== '' && eligibleTeamIds.has(affiliationTeamId)) {
    return affiliationTeamId
  }
  return defaultRegisterTeamId
}

function buildTarget(scope: AddModelTargetScope, href: string): AddModelTarget {
  return { scope, label: ADD_MODEL_LABELS[scope], href }
}

function personalTarget(routeTeamId: string, credentialId?: string): AddModelTarget {
  return buildTarget('personal', personalModelsRegisterHref(routeTeamId, credentialId))
}

function teamTarget(teamId: string, credentialId?: string): AddModelTarget {
  return buildTarget('team', teamModelsRegisterHref(teamId, credentialId))
}

function systemTarget(routeTeamId: string, credentialId?: string): AddModelTarget {
  return buildTarget('system', teamModelsRegisterHref(routeTeamId, credentialId, 'system'))
}

function targetsForAllScope(input: ResolveAddModelTargetsInput): readonly AddModelTarget[] {
  const { routeTeamId, credentialId, canRegisterTeam, isPlatformAdmin } = input
  const out: AddModelTarget[] = [personalTarget(routeTeamId, credentialId)]

  const registerTeamId = resolveRegisterTeamId(input)
  if (canRegisterTeam && registerTeamId) {
    out.push(teamTarget(registerTeamId, credentialId))
  }

  if (isPlatformAdmin) {
    out.push(systemTarget(routeTeamId, credentialId))
  }

  return out
}

export function resolveAddModelTargets(
  input: ResolveAddModelTargetsInput
): readonly AddModelTarget[] {
  const { scopeFilter, routeTeamId, credentialId, canRegisterTeam, isPlatformAdmin } = input

  if (scopeFilter === 'all') {
    return targetsForAllScope(input)
  }

  if (scopeFilter === 'personal') {
    return [personalTarget(routeTeamId, credentialId)]
  }

  if (scopeFilter === 'team') {
    const registerTeamId = resolveRegisterTeamId(input)
    if (!canRegisterTeam || !registerTeamId) {
      return []
    }
    return [teamTarget(registerTeamId, credentialId)]
  }

  if (!isPlatformAdmin) {
    return []
  }
  return [systemTarget(routeTeamId, credentialId)]
}
