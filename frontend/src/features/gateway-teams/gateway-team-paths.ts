/** Gateway 团队作用域路由（与 app-layout-routes teams/:teamId 对齐） */

export function gatewayTeamKeysHref(teamId: string | null | undefined): string {
  if (!teamId) return '/gateway/keys'
  return `/gateway/teams/${encodeURIComponent(teamId)}/keys`
}

export function gatewayTeamModelsHref(teamId: string | null | undefined): string {
  if (!teamId) return '/gateway/models'
  return `/gateway/teams/${encodeURIComponent(teamId)}/models`
}

export function gatewayTeamRoutesHref(teamId: string | null | undefined): string {
  if (!teamId) return '/gateway/routes'
  return `/gateway/teams/${encodeURIComponent(teamId)}/routes`
}
