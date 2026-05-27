import { useCallback, useMemo, useState } from 'react'

import type { GatewayCredentialUpdateBody, ProviderCredential } from '@/api/gateway'

import {
  apiBaseRequiredForProtocols,
  apiBasesFromCredential,
  compactApiBasesForSubmit,
  defaultApiBasesForProfile,
  primaryApiBaseFromForm,
  protocolsForProfile,
  type CredentialApiBasesFormState,
} from './credential-api-bases-utils'
import {
  compactExtra,
  extraToFormValues,
  type CredentialExtraValues,
} from './credential-extra-utils'
import {
  apiKeyLabelForProvider,
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
  profileDefaults: CredentialApiBasesFormState
  apiBasePlaceholder: string
  apiBaseRequired: boolean
  hasUnknownExtra: boolean
  profileOptions: ReturnType<typeof profilesForProvider>
  activeProfile: ReturnType<typeof getUpstreamProfileSpec>
  activeProtocols: ReturnType<typeof protocolsForProfile>
}

export interface UseCredentialEditFormResult extends CredentialEditFormDerived {
  name: string
  setName: (value: string) => void
  apiBases: CredentialApiBasesFormState
  setApiBases: (value: CredentialApiBasesFormState) => void
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
  const provider = cred.provider
  const schema = getProviderSchema(provider)
  const initialProfile = initialProfileId(cred)
  const initialActiveProfile = getUpstreamProfileSpec(provider, initialProfile || undefined)

  const [name, setName] = useState<string>(() => cred.name)
  const [apiBases, setApiBases] = useState<CredentialApiBasesFormState>(() =>
    apiBasesFromCredential(cred, initialActiveProfile, schema?.defaultApiBase)
  )
  const [apiKey, setApiKey] = useState<string>('')
  const [profileId, setProfileIdState] = useState<string>(() => initialProfile)
  const [extra, setExtra] = useState<CredentialExtraValues>(() => extraToFormValues(cred.extra))
  const [isActive, setIsActive] = useState<boolean>(() => cred.is_active)

  const profileOptions = useMemo(() => profilesForProvider(provider), [provider])
  const activeProfile = useMemo(
    () => getUpstreamProfileSpec(provider, profileId || undefined),
    [provider, profileId]
  )
  const profileDefaults = useMemo(
    () => defaultApiBasesForProfile(activeProfile, schema?.defaultApiBase),
    [activeProfile, schema?.defaultApiBase]
  )
  const activeProtocols = useMemo(
    () => protocolsForProfile(activeProfile, schema?.defaultApiBase),
    [activeProfile, schema?.defaultApiBase]
  )
  const extraFields = useMemo(() => extraFieldsForProvider(provider), [provider])
  const apiKeyLabel = apiKeyLabelForProvider(provider)
  const apiBasePlaceholder =
    schema?.apiBasePlaceholder ??
    activeProfile?.defaultApiBaseOpenai ??
    (profileDefaults.openai_compat.length > 0
      ? profileDefaults.openai_compat
      : 'https://example.com/v1')
  const apiBaseRequired = useMemo(
    () => apiBaseRequiredForProtocols(activeProtocols, schema?.apiBaseRequired),
    [activeProtocols, schema?.apiBaseRequired]
  )
  const apiBaseMissing = apiBaseRequired && !primaryApiBaseFromForm(apiBases)
  const requiredExtraMissing = extraFields.some((f) => f.required && !(extra[f.key] ?? '').trim())

  const origProfileId = useMemo(
    () => (cred.profile_id ?? '').trim() || (defaultProfileIdForProvider(provider) ?? ''),
    [cred.profile_id, provider]
  )
  const origApiBases = useMemo(
    () => apiBasesFromCredential(cred, initialActiveProfile, schema?.defaultApiBase),
    [cred, initialActiveProfile, schema?.defaultApiBase]
  )
  const apiBasesSynced =
    apiBases.openai_compat.trim() === origApiBases.openai_compat.trim() &&
    apiBases.anthropic_native.trim() === origApiBases.anthropic_native.trim()

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

  const synced =
    name === cred.name &&
    apiBasesSynced &&
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
    setApiBases(apiBasesFromCredential(cred, initialActiveProfile, schema?.defaultApiBase))
    setApiKey('')
    setProfileIdState(initialProfileId(cred))
    setExtra(extraToFormValues(cred.extra))
    setIsActive(cred.is_active)
  }, [cred, initialActiveProfile, schema?.defaultApiBase])

  const clearApiKey = useCallback((): void => {
    setApiKey('')
  }, [])

  const setProfileId = useCallback(
    (nextProfileId: string): void => {
      setProfileIdState(nextProfileId)
      const spec = getUpstreamProfileSpec(provider, nextProfileId)
      setApiBases(defaultApiBasesForProfile(spec, schema?.defaultApiBase))
    },
    [provider, schema?.defaultApiBase]
  )

  const buildUpdateBody = useCallback((): GatewayCredentialUpdateBody => {
    const submittedBases = compactApiBasesForSubmit(apiBases, profileDefaults)
    const body: GatewayCredentialUpdateBody = {
      api_base: apiBases.openai_compat.trim() || null,
      api_bases: submittedBases ?? null,
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
    apiBases,
    apiKey,
    compactedNow,
    configManaged,
    cred.profile_id,
    isActive,
    name,
    origProfileId,
    profileDefaults,
    profileId,
    trackIsActive,
  ])

  return {
    name,
    setName,
    apiBases,
    setApiBases,
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
    profileDefaults,
    apiBasePlaceholder,
    apiBaseRequired,
    hasUnknownExtra,
    profileOptions,
    activeProfile,
    activeProtocols,
  }
}
