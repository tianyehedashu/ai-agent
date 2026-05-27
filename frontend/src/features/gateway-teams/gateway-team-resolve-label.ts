/** 将 team_id 解析为展示名（纯函数，便于单测）。 */

export function resolveTeamLabelFromMap(
  teamNameById: ReadonlyMap<string, string>,
  teamId: string
): string {
  const trimmed = teamId.trim()
  if (!trimmed) return '—'
  return teamNameById.get(trimmed) ?? `${trimmed.slice(0, 8)}…`
}
