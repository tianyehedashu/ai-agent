/** 单 tenant 列表用量 Map key（personal / single-team） */
export function buildRouteUsageKey(routeName: string): string {
  return routeName
}

/** 跨团队协作团队用量 Map key（team_id + route_name，避免同名 route 碰撞） */
export function buildManagedTeamRouteUsageKey(teamId: string, routeName: string): string {
  return `${teamId}:${routeName}`
}
