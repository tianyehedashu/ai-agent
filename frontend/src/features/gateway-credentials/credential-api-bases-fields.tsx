import { memo, useCallback, useMemo } from 'react'

import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

import {
  type CredentialApiBasesFormState,
  type CredentialProtocolKey,
  protocolLabel,
  protocolsForProfile,
} from './credential-api-bases-utils'

import type { UpstreamProfileSpec } from './provider-schemas'

export interface CredentialApiBasesFieldsProps {
  idPrefix: string
  apiBases: CredentialApiBasesFormState
  onChange: (next: CredentialApiBasesFormState) => void
  activeProfile?: UpstreamProfileSpec
  providerDefaultApiBase?: string
  /** 父级已算好时传入，避免重复 protocolsForProfile */
  protocols?: readonly CredentialProtocolKey[]
  apiBaseRequired?: boolean
  showEffectiveHints?: boolean
  effectiveOpenai?: string | null
  effectiveAnthropic?: string | null
}

export const CredentialApiBasesFields = memo(function CredentialApiBasesFields({
  idPrefix,
  apiBases,
  onChange,
  activeProfile,
  providerDefaultApiBase,
  protocols: protocolsProp,
  apiBaseRequired = false,
  showEffectiveHints = false,
  effectiveOpenai,
  effectiveAnthropic,
}: CredentialApiBasesFieldsProps): React.JSX.Element {
  const protocols = useMemo(
    () => protocolsProp ?? protocolsForProfile(activeProfile, providerDefaultApiBase),
    [protocolsProp, activeProfile, providerDefaultApiBase]
  )

  const updateProtocol = useCallback(
    (protocol: CredentialProtocolKey, value: string): void => {
      onChange({ ...apiBases, [protocol]: value })
    },
    [apiBases, onChange]
  )

  return (
    <div className="space-y-3">
      {protocols.map((protocol) => {
        const required = apiBaseRequired && protocol === 'openai_compat' && protocols.length === 1
        const effective = protocol === 'openai_compat' ? effectiveOpenai : effectiveAnthropic
        return (
          <div key={protocol} className="space-y-2">
            <Label htmlFor={`${idPrefix}-${protocol}`}>
              {protocolLabel(protocol)}
              {required ? (
                <span className="ml-1 text-destructive">*</span>
              ) : (
                <span className="ml-1 text-[11px] text-muted-foreground">
                  （可选，留空用方案默认）
                </span>
              )}
            </Label>
            <Input
              id={`${idPrefix}-${protocol}`}
              type="url"
              value={apiBases[protocol]}
              onChange={(e) => {
                updateProtocol(protocol, e.target.value)
              }}
              placeholder={
                protocol === 'openai_compat'
                  ? (activeProfile?.defaultApiBaseOpenai ??
                    providerDefaultApiBase ??
                    'https://example.com/v1')
                  : (activeProfile?.defaultApiBaseAnthropic ?? 'https://example.com/anthropic')
              }
            />
            {protocol === 'anthropic_native' && activeProfile?.anthropicDirectHint ? (
              <p className="text-[11px] text-muted-foreground">
                {activeProfile.anthropicDirectHint}
              </p>
            ) : null}
            {protocol === 'openai_compat' ? (
              <p className="text-[11px] text-muted-foreground">
                经本 Gateway 代理与模型发现（probe）使用此根。
              </p>
            ) : null}
            {showEffectiveHints && effective ? (
              <p className="text-[11px] text-muted-foreground">
                解析后有效根：
                <span className="ml-1 font-mono text-[10px]">{effective}</span>
              </p>
            ) : null}
          </div>
        )
      })}
    </div>
  )
})
