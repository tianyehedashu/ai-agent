/**
 * 凭据多协议 endpoint 表单工具。
 */

import type { CredentialApiBases } from '@/api/gateway/credentials'

import type { UpstreamProfileSpec } from './provider-schemas'

export type CredentialProtocolKey = 'openai_compat' | 'anthropic_native'

export interface CredentialApiBasesFormState {
  openai_compat: string
  anthropic_native: string
}

export const EMPTY_API_BASES_FORM: CredentialApiBasesFormState = {
  openai_compat: '',
  anthropic_native: '',
}

const PROTOCOL_LABELS: Record<CredentialProtocolKey, string> = {
  openai_compat: 'OpenAI-compat 根',
  anthropic_native: 'Anthropic-native 根',
}

export function protocolLabel(protocol: CredentialProtocolKey): string {
  return PROTOCOL_LABELS[protocol]
}

export function protocolsForProfile(
  profile: UpstreamProfileSpec | undefined,
  providerDefaultApiBase?: string
): readonly CredentialProtocolKey[] {
  const out: CredentialProtocolKey[] = []
  if (profile?.defaultApiBaseOpenai || providerDefaultApiBase) {
    out.push('openai_compat')
  }
  if (profile?.defaultApiBaseAnthropic) {
    out.push('anthropic_native')
  }
  if (out.length === 0) {
    out.push('openai_compat')
  }
  return out
}

export function defaultApiBasesForProfile(
  profile: UpstreamProfileSpec | undefined,
  providerDefaultApiBase?: string
): CredentialApiBasesFormState {
  return {
    openai_compat: profile?.defaultApiBaseOpenai ?? providerDefaultApiBase ?? '',
    anthropic_native: profile?.defaultApiBaseAnthropic ?? '',
  }
}

export function apiBasesFromCredential(
  cred: { api_bases?: CredentialApiBases | null; api_base?: string | null },
  profile: UpstreamProfileSpec | undefined,
  providerDefaultApiBase?: string
): CredentialApiBasesFormState {
  const defaults = defaultApiBasesForProfile(profile, providerDefaultApiBase)
  return {
    openai_compat: cred.api_bases?.openai_compat ?? cred.api_base ?? defaults.openai_compat,
    anthropic_native: cred.api_bases?.anthropic_native ?? defaults.anthropic_native,
  }
}

export function compactApiBasesForSubmit(
  form: CredentialApiBasesFormState,
  defaults: CredentialApiBasesFormState
): CredentialApiBases | undefined {
  const out: CredentialApiBases = {}
  const openai = form.openai_compat.trim()
  const anthropic = form.anthropic_native.trim()
  const defaultOpenai = defaults.openai_compat.trim()
  const defaultAnthropic = defaults.anthropic_native.trim()

  if (openai && openai !== defaultOpenai) {
    out.openai_compat = openai
  }
  if (anthropic && anthropic !== defaultAnthropic) {
    out.anthropic_native = anthropic
  }
  if (Object.keys(out).length === 0) {
    return undefined
  }
  return out
}

export function apiBaseRequiredForProtocols(
  protocols: readonly CredentialProtocolKey[],
  apiBaseRequired?: boolean
): boolean {
  if (apiBaseRequired) return true
  return protocols.includes('openai_compat') && !protocols.includes('anthropic_native')
}

export function primaryApiBaseFromForm(form: CredentialApiBasesFormState): string {
  return form.openai_compat.trim() || form.anthropic_native.trim()
}
