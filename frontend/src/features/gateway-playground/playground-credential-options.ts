/**
 * 调用指南 / Playground 凭据下拉：团队 summaries + 个人 my-credentials，按数据权限合并。
 */

import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import { gatewayApi, type CredentialSummary, type ProviderCredential } from '@/api/gateway'
import { useGatewayCredentialDirectory } from '@/features/gateway-credentials/use-credential-directory'

export type PlaygroundCredentialOption = CredentialSummary

export function personalCredentialToSummary(c: ProviderCredential): PlaygroundCredentialOption {
  return {
    id: c.id,
    provider: c.provider,
    name: c.name,
    scope: 'user',
    is_active: c.is_active,
    is_config_managed: c.is_config_managed ?? false,
  }
}

export function mergePlaygroundCredentialOptions(
  teamSummaries: readonly CredentialSummary[],
  personalCredentials: readonly ProviderCredential[]
): PlaygroundCredentialOption[] {
  const byId = new Map<string, PlaygroundCredentialOption>()
  for (const c of teamSummaries) {
    byId.set(c.id, c)
  }
  for (const c of personalCredentials) {
    byId.set(c.id, personalCredentialToSummary(c))
  }
  return Array.from(byId.values())
}

/** 仅展示启用凭据；当前已选但已停用的项仍保留（与模型页一致） */
export function filterPlaygroundCredentialOptions(
  options: readonly PlaygroundCredentialOption[],
  selectedCredentialId: string
): PlaygroundCredentialOption[] {
  return options.filter((c) => c.is_active || c.id === selectedCredentialId)
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

export interface UsePlaygroundCredentialOptionsReturn {
  grouped: PlaygroundCredentialGroups
  byId: Map<string, PlaygroundCredentialOption>
  isLoading: boolean
  isEmpty: boolean
}

export function usePlaygroundCredentialOptions(
  selectedCredentialId: string
): UsePlaygroundCredentialOptionsReturn {
  const { list: teamSummaries, isLoading: teamLoading } = useGatewayCredentialDirectory()
  const { data: personalCredentials = [], isLoading: personalLoading } = useQuery({
    queryKey: ['gateway', 'my-credentials'],
    queryFn: () => gatewayApi.listMyCredentials(),
  })

  const allOptions = useMemo(
    () => mergePlaygroundCredentialOptions(teamSummaries, personalCredentials),
    [teamSummaries, personalCredentials]
  )

  const selectableOptions = useMemo(
    () => filterPlaygroundCredentialOptions(allOptions, selectedCredentialId),
    [allOptions, selectedCredentialId]
  )

  const grouped = useMemo(
    () => groupPlaygroundCredentialOptions(selectableOptions),
    [selectableOptions]
  )

  const byId = useMemo(() => new Map(allOptions.map((c) => [c.id, c])), [allOptions])

  return {
    grouped,
    byId,
    isLoading: teamLoading || personalLoading,
    isEmpty: selectableOptions.length === 0,
  }
}
