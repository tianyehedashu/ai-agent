/**
 * 「新增凭据」弹窗表单初始态与 open 生命周期工具。
 *
 * 表单重置必须仅在 open false→true 时执行；writableTeams / provider-profiles
 * 异步加载不得清空用户已填字段（见 create-credential-dialog.tsx）。
 */

import type { GatewayTeam } from '@/api/gateway/teams'

import {
  defaultApiBasesForProfile,
  type CredentialApiBasesFormState,
} from './credential-api-bases-utils'
import {
  defaultProfileIdForProvider,
  getProviderSchema,
  getUpstreamProfileSpec,
  providersForScope,
  type CredentialFormScope,
} from './provider-schemas'

import type { CredentialExtraValues } from './credential-extra-utils'

export interface CreateCredentialFormState {
  scope: CredentialFormScope
  provider: string
  name: string
  apiKey: string
  apiBases: CredentialApiBasesFormState
  profileId: string
  extra: CredentialExtraValues
  teamId: string
}

export interface BuildCreateCredentialFormStateInput {
  resolvedDefaultScope: CredentialFormScope
  defaultProvider?: string
  defaultTeamId?: string
  teamOptions: readonly GatewayTeam[]
}

export function resolveInitialTeamId(
  writableTeams: readonly GatewayTeam[],
  defaultTeamId: string | undefined
): string {
  if (defaultTeamId && writableTeams.some((team) => team.id === defaultTeamId)) {
    return defaultTeamId
  }
  return writableTeams[0]?.id ?? ''
}

export function buildCreateCredentialFormState(
  input: BuildCreateCredentialFormStateInput
): CreateCredentialFormState {
  const { resolvedDefaultScope, defaultProvider, defaultTeamId, teamOptions } = input
  const candidates = providersForScope(resolvedDefaultScope)
  const initialProvider =
    defaultProvider && candidates.some((p) => p.id === defaultProvider)
      ? defaultProvider
      : (candidates[0]?.id ?? '')
  const initialProfile = defaultProfileIdForProvider(initialProvider) ?? ''
  const initialProfileSpec = getUpstreamProfileSpec(initialProvider, initialProfile || undefined)
  const initialSchema = getProviderSchema(initialProvider)

  return {
    scope: resolvedDefaultScope,
    provider: initialProvider,
    name: '',
    apiKey: '',
    profileId: initialProfile,
    apiBases: defaultApiBasesForProfile(initialProfileSpec, initialSchema?.defaultApiBase),
    extra: {},
    teamId: resolveInitialTeamId(teamOptions, defaultTeamId),
  }
}

/** 仅在 open 从 false 变为 true 时返回 true，避免异步依赖变更清空已填表单。 */
export function shouldInitializeCreateCredentialForm(open: boolean, wasOpen: boolean): boolean {
  return open && !wasOpen
}
