import { useCallback, useMemo, useState } from 'react'

import type { GatewayCredentialUpdateBody, ProviderCredential } from '@/api/gateway'

import {
  compactExtra,
  extraToFormValues,
  type CredentialExtraValues,
} from './credential-extra-utils'
import {
  apiKeyLabelForProvider,
  defaultApiBaseForProvider,
  defaultProfileIdForProvider,
  extraFieldsForProvider,
  getProviderSchema,
  getUpstreamProfileSpec,
  profilesForProvider,
} from './provider-schemas'

export interface UseCredentialEditFormOptions {
  cred: ProviderCredential
  /** 托管 system 凭据禁止改名 */
  configManaged?: boolean
  /** personal 编辑含 is_active */
  trackIsActive?: boolean
}

export interface CredentialEditFormDerived {
  provider: string
  apiKeyLabel: string
  extraFields: ReturnType<typeof extraFieldsForProvider>
  schema: ReturnType<typeof getProviderSchema>
  defaultApiBase: string
  baseIsDefault: boolean
  apiBasePlaceholder: string
  apiBaseRequired: boolean
  hasUnknownExtra: boolean
  profileOptions: ReturnType<typeof profilesForProvider>
  activeProfile: ReturnType<typeof getUpstreamProfileSpec>
}

export interface UseCredentialEditFormResult extends CredentialEditFormDerived {
  name: string
  setName: (value: string) => void
  apiBase: string
  setApiBase: (value: string) => void
  apiKey: string
  setApiKey: (value: string) => void
  profileId: string
  setProfileId: (value: string) => void
  extra: CredentialExtraValues
  setExtra: (value: CredentialExtraValues) => void
  isActive: boolean
  setIsActive: (value: boolean) => void
  canSave: boolean
  buildUpdateBody: () => GatewayCredentialUpdateBody
  reset: () => void
  clearApiKey: () => void
}

function initialProfileId(cred: ProviderCredential): string {
  if (cred.profile_id?.trim()) {
    return cred.profile_id.trim()
  }
  return defaultProfileIdForProvider(cred.provider) ?? ''
}

export function useCredentialEditForm({
  cred,
  configManaged = false,
  trackIsActive = false,
}: UseCredentialEditFormOptions): UseCredentialEditFormResult {
  const [name, setName] = useState<string>(() => cred.name)
  const [apiBase, setApiBase] = useState<string>(() => cred.api_base ?? '')
  const [apiKey, setApiKey] = useState<string>('')
  const [profileId, setProfileIdState] = useState<string>(() => initialProfileId(cred))
  const [extra, setExtra] = useState<CredentialExtraValues>(() => extraToFormValues(cred.extra))
  const [isActive, setIsActive] = useState<boolean>(() => cred.is_active)

  const provider = cred.provider
  const schema = getProviderSchema(provider)
  const profileOptions = useMemo(() => profilesForProvider(provider), [provider])
  const activeProfile = useMemo(
    () => getUpstreamProfileSpec(provider, profileId || undefined),
    [provider, profileId]
  )
  const extraFields = useMemo(() => extraFieldsForProvider(provider), [provider])
  const apiKeyLabel = apiKeyLabelForProvider(provider)
  const defaultApiBase = defaultApiBaseForProvider(provider, profileId || undefined)
  const baseIsDefault = defaultApiBase.length > 0 && apiBase === defaultApiBase
  const apiBasePlaceholder =
    schema?.apiBasePlaceholder ??
    activeProfile?.defaultApiBaseOpenai ??
    (defaultApiBase.length > 0 ? defaultApiBase : 'https://example.com/v1')
  const apiBaseRequired = schema?.apiBaseRequired ?? false
  const apiBaseMissing = apiBaseRequired && !apiBase.trim()
  const requiredExtraMissing = extraFields.some((f) => f.required && !(extra[f.key] ?? '').trim())

  const compactedNow = useMemo(() => compactExtra(extra), [extra])
  const compactedOrig = useMemo(() => compactExtra(extraToFormValues(cred.extra)), [cred.extra])
  const extraSynced = useMemo(() => {
    const nowKeys = Object.keys(compactedNow)
    const origKeys = Object.keys(compactedOrig)
    if (nowKeys.length !== origKeys.length) return false
    for (const key of nowKeys) {
      if (compactedNow[key] !== compactedOrig[key]) return false
    }
    return true
  }, [compactedNow, compactedOrig])

  const origProfileId =
    (cred.profile_id ?? '').trim() || (defaultProfileIdForProvider(provider) ?? '')
  const synced =
    name === cred.name &&
    (apiBase.trim() || '') === (cred.api_base ?? '') &&
    apiKey === '' &&
    (profileId.trim() || '') === origProfileId &&
    extraSynced &&
    (!trackIsActive || isActive === cred.is_active)

  const canSave = Boolean(name.trim()) && !apiBaseMissing && !requiredExtraMissing && !synced

  const credExtra = cred.extra
  const hasUnknownExtra =
    extraFields.length === 0 && credExtra !== null && Object.keys(credExtra).length > 0

  const reset = useCallback((): void => {
    setName(cred.name)
    setApiBase(cred.api_base ?? '')
    setApiKey('')
    setProfileIdState(initialProfileId(cred))
    setExtra(extraToFormValues(cred.extra))
    setIsActive(cred.is_active)
  }, [cred])

  const clearApiKey = useCallback((): void => {
    setApiKey('')
  }, [])

  const setProfileId = useCallback(
    (nextProfileId: string): void => {
      setProfileIdState(nextProfileId)
      const spec = getUpstreamProfileSpec(provider, nextProfileId)
      if (spec?.defaultApiBaseOpenai) {
        setApiBase(spec.defaultApiBaseOpenai)
      }
    },
    [provider]
  )

  const buildUpdateBody = useCallback((): GatewayCredentialUpdateBody => {
    const body: GatewayCredentialUpdateBody = {
      api_base: apiBase.trim() || null,
      extra: Object.keys(compactedNow).length > 0 ? compactedNow : null,
    }
    if (!configManaged) {
      body.name = name.trim()
    }
    if (apiKey.trim()) {
      body.api_key = apiKey.trim()
    }
    if (trackIsActive) {
      body.is_active = isActive
    }
    const trimmedProfile = profileId.trim()
    if (trimmedProfile && trimmedProfile !== origProfileId) {
      body.profile_id = trimmedProfile
    } else if (!trimmedProfile && cred.profile_id) {
      body.profile_id = null
    }
    return body
  }, [
    apiBase,
    apiKey,
    compactedNow,
    configManaged,
    cred.profile_id,
    isActive,
    name,
    origProfileId,
    profileId,
    trackIsActive,
  ])

  return {
    name,
    setName,
    apiBase,
    setApiBase,
    apiKey,
    setApiKey,
    profileId,
    setProfileId,
    extra,
    setExtra,
    isActive,
    setIsActive,
    canSave,
    buildUpdateBody,
    reset,
    clearApiKey,
    provider,
    apiKeyLabel,
    extraFields,
    schema,
    defaultApiBase,
    baseIsDefault,
    apiBasePlaceholder,
    apiBaseRequired,
    hasUnknownExtra,
    profileOptions,
    activeProfile,
  }
}
