/**
 * Playground / 调用指南凭据下拉：后端聚合个人 + 各团队 + 系统凭据。
 */

import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import type { PlaygroundCredentialSummary } from '@/api/gateway'
import { useGatewayWorkspaceTeamId } from '@/hooks/use-gateway-team-id'
import { useGatewayTeamStore } from '@/stores/gateway-team'

import { fetchPlaygroundCredentialSummaries } from './playground-credential-summaries'

export type PlaygroundCredentialOption = PlaygroundCredentialSummary

export const PLAYGROUND_CREDENTIAL_SUMMARIES_QUERY_KEY = [
  'gateway',
  'playground',
  'credential-summaries',
] as const

/** 调用指南可选凭据：membership 内且已启用（与 backend playground_credential_reads 语义一致） */
export function isPlaygroundCredentialSelectable(
  c: PlaygroundCredentialOption,
  membershipTeamIds: ReadonlySet<string>
): boolean {
  if (!c.is_active) return false
  if (c.scope === 'user') return true
  const teamId = c.context_team_id
  return Boolean(teamId && membershipTeamIds.has(teamId))
}

export function filterPlaygroundCredentialOptions(
  options: readonly PlaygroundCredentialOption[],
  membershipTeamIds: ReadonlySet<string>
): PlaygroundCredentialOption[] {
  return options.filter((c) => isPlaygroundCredentialSelectable(c, membershipTeamIds))
}

export interface PlaygroundCredentialGroups {
  personal: PlaygroundCredentialOption[]
  team: PlaygroundCredentialOption[]
  system: PlaygroundCredentialOption[]
}

export function groupPlaygroundCredentialOptions(
  options: readonly PlaygroundCredentialOption[]
): PlaygroundCredentialGroups {
  const personal: PlaygroundCredentialOption[] = []
  const team: PlaygroundCredentialOption[] = []
  const system: PlaygroundCredentialOption[] = []
  for (const c of options) {
    if (c.scope === 'user') personal.push(c)
    else if (c.scope === 'system') system.push(c)
    else team.push(c)
  }
  const byName = (a: PlaygroundCredentialOption, b: PlaygroundCredentialOption): number =>
    a.name.localeCompare(b.name)
  personal.sort(byName)
  team.sort(byName)
  system.sort(byName)
  return { personal, team, system }
}

export function isPersonalPlaygroundCredential(
  byId: ReadonlyMap<string, PlaygroundCredentialOption>,
  credentialId: string
): boolean {
  if (!credentialId) return false
  return byId.get(credentialId)?.scope === 'user'
}

/** 解析模型/Key 请求所用的 teamId */
export function resolvePlaygroundContextTeamId(
  credentialId: string,
  byId: ReadonlyMap<string, PlaygroundCredentialOption>,
  workspaceTeamId: string | null
): string | null {
  if (!credentialId) return workspaceTeamId
  const cred = byId.get(credentialId)
  if (!cred || cred.scope === 'user') return workspaceTeamId
  return cred.context_team_id ?? workspaceTeamId
}

export interface UsePlaygroundCredentialOptionsReturn {
  grouped: PlaygroundCredentialGroups
  byId: Map<string, PlaygroundCredentialOption>
  workspaceTeamId: string | null
  isLoading: boolean
  isFetching: boolean
  isEmpty: boolean
}

export function usePlaygroundCredentialOptions(): UsePlaygroundCredentialOptionsReturn {
  const workspaceTeamId = useGatewayWorkspaceTeamId()
  const teams = useGatewayTeamStore((s) => s.teams)
  const {
    data: allOptions = [],
    isLoading,
    isFetching,
  } = useQuery({
    queryKey: [...PLAYGROUND_CREDENTIAL_SUMMARIES_QUERY_KEY, teams.map((t) => t.id).join(',')],
    queryFn: () => fetchPlaygroundCredentialSummaries(teams),
    enabled: teams.length > 0,
  })

  const membershipTeamIds = useMemo(() => new Set(teams.map((t) => t.id)), [teams])

  const selectableOptions = useMemo(
    () => filterPlaygroundCredentialOptions(allOptions, membershipTeamIds),
    [allOptions, membershipTeamIds]
  )

  const grouped = useMemo(
    () => groupPlaygroundCredentialOptions(selectableOptions),
    [selectableOptions]
  )

  const byId = useMemo(() => new Map(selectableOptions.map((c) => [c.id, c])), [selectableOptions])

  return {
    grouped,
    byId,
    workspaceTeamId,
    isLoading,
    isFetching,
    isEmpty: selectableOptions.length === 0,
  }
}
