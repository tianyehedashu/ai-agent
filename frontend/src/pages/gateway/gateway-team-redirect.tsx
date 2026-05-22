/**
 * Gateway 入口：无 team 上下文时重定向到当前/personal team 工作区。
 */

import { Navigate, useLocation } from 'react-router-dom'

import { useGatewayTeamStore } from '@/stores/gateway-team'

const FLAT_ROUTES = new Set(['guide', 'platform-stats'])

const LEGACY_TEAM_SEGMENTS = new Set([
  'overview',
  'keys',
  'credentials',
  'models',
  'routes',
  'budgets',
  'logs',
  'teams',
  'pricing',
])

export default function GatewayTeamRedirect(): React.JSX.Element {
  const location = useLocation()
  const currentTeamId = useGatewayTeamStore((s) => s.currentTeamId)
  const teams = useGatewayTeamStore((s) => s.teams)

  let preferredTeamId: string | null = currentTeamId
  if (!preferredTeamId) {
    const personal = teams.find((t) => t.kind === 'personal')
    if (personal) {
      preferredTeamId = personal.id
    } else if (teams[0]) {
      preferredTeamId = teams[0].id
    }
  }

  const legacyMatch = /^\/gateway\/([^/]+)(\/.*)?$/.exec(location.pathname)
  if (legacyMatch && preferredTeamId) {
    const first = legacyMatch[1]
    const rest = typeof legacyMatch[2] === 'string' ? legacyMatch[2] : ''
    if (!FLAT_ROUTES.has(first) && LEGACY_TEAM_SEGMENTS.has(first)) {
      const mappedFirst = first === 'teams' ? 'members' : first
      return <Navigate to={`/gateway/teams/${preferredTeamId}/${mappedFirst}${rest}`} replace />
    }
  }

  if (preferredTeamId) {
    return <Navigate to={`/gateway/teams/${preferredTeamId}/overview`} replace />
  }

  return <Navigate to="/gateway/guide" replace />
}
