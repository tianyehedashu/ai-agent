import { useMemo } from 'react'

import type { VirtualKeyTeamGrant } from '@/api/gateway/grants'

/** 从 grant 列表构建 slug → grant 映射（reveal hint / Banner 共用） */
export function useTeamSlugMap(grants: VirtualKeyTeamGrant[]): Map<string, VirtualKeyTeamGrant> {
  return useMemo(() => {
    const map = new Map<string, VirtualKeyTeamGrant>()
    for (const g of grants) {
      if (g.granted_team_slug) map.set(g.granted_team_slug, g)
    }
    return map
  }, [grants])
}

/** 检测跨 grant team 同名模型（用于 Banner 提示） */
export function findHomonymModels(grants: VirtualKeyTeamGrant[]): string[] {
  const nameToTeams = new Map<string, Set<string>>()
  for (const g of grants) {
    for (const name of g.registered_model_names ?? []) {
      const teams = nameToTeams.get(name) ?? new Set<string>()
      teams.add(g.granted_team_slug ?? g.tenant_id)
      nameToTeams.set(name, teams)
    }
  }
  return [...nameToTeams.entries()]
    .filter(([, teams]) => teams.size >= 2)
    .map(([name]) => name)
    .sort()
}
