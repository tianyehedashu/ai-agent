function teamBase(teamId: string): string {
  return `/gateway/teams/${encodeURIComponent(teamId)}`
}

/** Admin 配额中心页 */
export function budgetsAdminHref(
  teamId: string,
  params?: { layer?: string; model?: string; credential?: string; user?: string }
): string {
  const search = new URLSearchParams()
  if (params?.layer) search.set('layer', params.layer)
  if (params?.model) search.set('model', params.model)
  if (params?.credential) search.set('credential_id', params.credential)
  if (params?.user) search.set('user_id', params.user)
  const qs = search.toString()
  return qs ? `${teamBase(teamId)}/budgets?${qs}` : `${teamBase(teamId)}/budgets`
}
