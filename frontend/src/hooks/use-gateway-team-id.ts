/**
 * 从 Gateway 路由读取当前 teamId，并与 gateway-team store 同步。
 */

import { useEffect } from 'react'

import { useParams } from 'react-router-dom'

import { useGatewayTeamStore } from '@/stores/gateway-team'

export function useGatewayTeamId(): string {
  const { teamId } = useParams<{ teamId: string }>()
  const setCurrentTeamId = useGatewayTeamStore((s) => s.setCurrentTeamId)

  useEffect(() => {
    if (teamId) {
      setCurrentTeamId(teamId)
    }
  }, [teamId, setCurrentTeamId])

  if (!teamId) {
    throw new Error('Missing route param :teamId for Gateway team workspace')
  }
  return teamId
}

/** 可选 teamId（Guide 等无团队路由） */
export function useOptionalGatewayTeamId(): string | null {
  const { teamId } = useParams<{ teamId?: string }>()
  const setCurrentTeamId = useGatewayTeamStore((s) => s.setCurrentTeamId)

  useEffect(() => {
    if (teamId) {
      setCurrentTeamId(teamId)
    }
  }, [teamId, setCurrentTeamId])

  return teamId ?? null
}
