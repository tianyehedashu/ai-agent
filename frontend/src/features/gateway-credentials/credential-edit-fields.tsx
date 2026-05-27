import type { ProviderCredential } from '@/api/gateway'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'

import { CredentialApiBasesFields } from './credential-api-bases-fields'
import { ExtraFieldsRenderer } from './credential-extra-fields'
import { CurrentApiKeyField } from './current-api-key-field'

import type { UseCredentialEditFormResult } from './use-credential-edit-form'

export interface CredentialEditFieldsProps {
  cred: ProviderCredential
  idPrefix: string
  form: UseCredentialEditFormResult
  configManaged?: boolean
  showActiveSwitch?: boolean
  revealFn: () => Promise<{ api_key: string }>
  canReveal?: boolean
  editable?: boolean
}

export function CredentialEditFields({
  cred,
  idPrefix,
  form,
  configManaged = false,
  showActiveSwitch = false,
  revealFn,
  canReveal = true,
  editable = true,
}: CredentialEditFieldsProps): React.JSX.Element {
  const {
    name,
    setName,
    apiKey,
    setApiKey,
    apiBases,
    setApiBases,
    extra,
    setExtra,
    isActive,
    setIsActive,
    apiKeyLabel,
    extraFields,
    schema,
    apiBaseRequired,
    hasUnknownExtra,
    profileId,
    setProfileId,
    profileOptions,
    activeProfile,
    activeProtocols,
    clearApiKey,
  } = form

  const credExtra = cred.extra

  return (
    <>
      {showActiveSwitch ? (
        <div className="flex items-center justify-between rounded-md border px-3 py-2">
          <Label htmlFor={`${idPrefix}-active`} className="cursor-pointer font-normal">
            启用该账号
          </Label>
          <Switch id={`${idPrefix}-active`} checked={isActive} onCheckedChange={setIsActive} />
        </div>
      ) : null}
      <CurrentApiKeyField
        label={apiKeyLabel}
        maskedValue={cred.api_key_masked}
        revealFn={revealFn}
        canReveal={canReveal}
        editable={editable}
        newKeyValue={apiKey}
        onNewKeyValueChange={(value) => {
          if (value === '') {
            clearApiKey()
            return
          }
          setApiKey(value)
        }}
        apiKeyPlaceholder={schema?.apiKeyPlaceholder}
        apiKeyHelpText={schema?.apiKeyHelpText}
      />
      {editable ? (
        <>
          <div className={showActiveSwitch ? 'space-y-2' : undefined}>
            <Label htmlFor={`${idPrefix}-name`}>{showActiveSwitch ? '账号名称' : '名称'}</Label>
            <Input
              id={`${idPrefix}-name`}
              className={showActiveSwitch ? undefined : 'mt-1.5'}
              value={name}
              readOnly={configManaged}
              disabled={configManaged}
              onChange={(e) => {
                setName(e.target.value)
              }}
            />
            {configManaged ? (
              <p className="mt-1 text-xs text-muted-foreground">
                该凭据由 app.toml / 环境变量同步维护，重命名会导致重复凭据。
              </p>
            ) : null}
          </div>
          {profileOptions.length > 1 ? (
            <div className={showActiveSwitch ? 'space-y-2' : undefined}>
              <Label htmlFor={`${idPrefix}-profile`}>方案</Label>
              <Select value={profileId} onValueChange={setProfileId}>
                <SelectTrigger
                  id={`${idPrefix}-profile`}
                  className={showActiveSwitch ? undefined : 'mt-1.5'}
                >
                  <SelectValue placeholder="选择上游方案" />
                </SelectTrigger>
                <SelectContent>
                  {profileOptions.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {activeProfile?.anthropicDirectHint ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  {activeProfile.anthropicDirectHint}
                </p>
              ) : null}
            </div>
          ) : null}
          <CredentialApiBasesFields
            idPrefix={`${idPrefix}-bases`}
            apiBases={apiBases}
            onChange={setApiBases}
            activeProfile={activeProfile}
            providerDefaultApiBase={schema?.defaultApiBase}
            protocols={activeProtocols}
            apiBaseRequired={apiBaseRequired}
            showEffectiveHints
            effectiveOpenai={cred.effective_api_base_openai}
            effectiveAnthropic={cred.effective_api_base_anthropic}
          />
          {extraFields.length > 0 ? (
            <ExtraFieldsRenderer
              fields={extraFields}
              values={extra}
              onChange={setExtra}
              idPrefix={`${idPrefix}-extra`}
            />
          ) : hasUnknownExtra ? (
            <div>
              <Label>extra（未知字段，只读）</Label>
              <pre className="mt-1.5 max-h-40 overflow-auto rounded-md border bg-muted/30 p-2 font-mono text-[11px] leading-relaxed">
                {JSON.stringify(credExtra, null, 2)}
              </pre>
              <p className="mt-1 text-xs text-muted-foreground">
                当前 provider 未声明 extra schema；如需编辑请在 schema 中追加字段。
              </p>
            </div>
          ) : null}
        </>
      ) : (
        <p className="text-sm text-muted-foreground">你无权编辑此凭据（系统凭据需平台管理员）。</p>
      )}
    </>
  )
}
