/**
 * 将后端 provider-profiles API 合并进表单用的 profile 列表（静态 schema 为兜底）。
 */

import type { ProviderProfileItem } from '@/api/gateway/provider-profiles'

import type { UpstreamProfileSpec } from './provider-schemas'

let remoteProfilesByProvider: ReadonlyMap<string, readonly UpstreamProfileSpec[]> | null = null

function toSpec(item: ProviderProfileItem): UpstreamProfileSpec {
  const anthropic = item.api_bases.anthropic_native
  return {
    id: item.id,
    label: item.label,
    defaultApiBaseOpenai: item.api_bases.openai_compat ?? undefined,
    defaultApiBaseAnthropic: anthropic ?? undefined,
    anthropicDirectHint:
      anthropic && item.provider === 'volcengine' ? `Claude Code 直连根：${anthropic}` : undefined,
    probeStrategy: item.probe_strategy,
    probeProtocol: item.probe_protocol,
    probeSupported: item.probe_supported,
  }
}

export function applyRemoteProviderProfiles(profiles: readonly ProviderProfileItem[]): void {
  const byProvider = new Map<string, UpstreamProfileSpec[]>()
  for (const item of profiles) {
    const list = byProvider.get(item.provider) ?? []
    list.push(toSpec(item))
    byProvider.set(item.provider, list)
  }
  remoteProfilesByProvider = byProvider
}

export function remoteProfilesForProvider(
  providerId: string
): readonly UpstreamProfileSpec[] | undefined {
  return remoteProfilesByProvider?.get(providerId)
}

export function clearRemoteProviderProfilesForTests(): void {
  remoteProfilesByProvider = null
}
