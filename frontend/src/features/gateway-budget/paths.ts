function teamBase(teamId: string): string {
  return `/gateway/teams/${encodeURIComponent(teamId)}`
}

/** Admin 预算管理页 */
export function budgetsAdminHref(
  teamId: string,
  params?: { tab?: string; model?: string }
): string {
  const search = new URLSearchParams()
  if (params?.tab) search.set('tab', params.tab)
  if (params?.model) search.set('model', params.model)
  const qs = search.toString()
  return qs ? `${teamBase(teamId)}/budgets?${qs}` : `${teamBase(teamId)}/budgets`
}
