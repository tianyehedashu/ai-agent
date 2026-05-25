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
  extraFieldsForProvider,
  getProviderSchema,
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
}

export interface UseCredentialEditFormResult extends CredentialEditFormDerived {
  name: string
  setName: (value: string) => void
  apiBase: string
  setApiBase: (value: string) => void
  apiKey: string
  setApiKey: (value: string) => void
  extra: CredentialExtraValues
  setExtra: (value: CredentialExtraValues) => void
  isActive: boolean
  setIsActive: (value: boolean) => void
  canSave: boolean
  buildUpdateBody: () => GatewayCredentialUpdateBody
  reset: () => void
  clearApiKey: () => void
}

export function useCredentialEditForm({
  cred,
  configManaged = false,
  trackIsActive = false,
}: UseCredentialEditFormOptions): UseCredentialEditFormResult {
  const [name, setName] = useState<string>(() => cred.name)
  const [apiBase, setApiBase] = useState<string>(() => cred.api_base ?? '')
  const [apiKey, setApiKey] = useState<string>('')
  const [extra, setExtra] = useState<CredentialExtraValues>(() => extraToFormValues(cred.extra))
  const [isActive, setIsActive] = useState<boolean>(() => cred.is_active)

  const provider = cred.provider
  const schema = getProviderSchema(provider)
  const extraFields = useMemo(() => extraFieldsForProvider(provider), [provider])
  const apiKeyLabel = apiKeyLabelForProvider(provider)
  const defaultApiBase = defaultApiBaseForProvider(provider)
  const baseIsDefault = defaultApiBase.length > 0 && apiBase === defaultApiBase
  const apiBasePlaceholder =
    schema?.apiBasePlaceholder ??
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
  const synced =
    name === cred.name &&
    (apiBase.trim() || '') === (cred.api_base ?? '') &&
    apiKey === '' &&
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
    setExtra(extraToFormValues(cred.extra))
    setIsActive(cred.is_active)
  }, [cred])

  const clearApiKey = useCallback((): void => {
    setApiKey('')
  }, [])

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
    return body
  }, [apiBase, apiKey, compactedNow, configManaged, isActive, name, trackIsActive])

  return {
    name,
    setName,
    apiBase,
    setApiBase,
    apiKey,
    setApiKey,
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
  }
}
