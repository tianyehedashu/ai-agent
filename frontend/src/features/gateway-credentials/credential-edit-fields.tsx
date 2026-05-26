import type { ProviderCredential } from '@/api/gateway'
import { Badge } from '@/components/ui/badge'
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
    apiBase,
    setApiBase,
    extra,
    setExtra,
    isActive,
    setIsActive,
    apiKeyLabel,
    extraFields,
    schema,
    defaultApiBase,
    baseIsDefault,
    apiBasePlaceholder,
    apiBaseRequired,
    hasUnknownExtra,
    profileId,
    setProfileId,
    profileOptions,
    activeProfile,
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
          <div className={showActiveSwitch ? 'space-y-2' : undefined}>
            <Label htmlFor={`${idPrefix}-new-key`}>新 {apiKeyLabel}（留空则不变）</Label>
            <Input
              id={`${idPrefix}-new-key`}
              type="password"
              autoComplete="new-password"
              className={showActiveSwitch ? undefined : 'mt-1.5'}
              value={apiKey}
              onChange={(e) => {
                setApiKey(e.target.value)
              }}
              placeholder={schema?.apiKeyPlaceholder}
            />
            {schema?.apiKeyHelpText ? (
              <p className="mt-1 text-xs text-muted-foreground">{schema.apiKeyHelpText}</p>
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
          <div className={showActiveSwitch ? 'space-y-2' : undefined}>
            <div className="flex items-center gap-2">
              <Label htmlFor={`${idPrefix}-base`}>
                {showActiveSwitch ? 'API Base' : 'api_base'}
                {apiBaseRequired ? (
                  <span className="ml-1 text-destructive">*</span>
                ) : (
                  <span className="ml-1 text-[11px] text-muted-foreground">（可选）</span>
                )}
              </Label>
              {baseIsDefault ? (
                <Badge variant="outline" className="px-1 py-0 text-[10px]">
                  默认
                </Badge>
              ) : null}
            </div>
            <Input
              id={`${idPrefix}-base`}
              type={showActiveSwitch ? 'url' : undefined}
              className={showActiveSwitch ? undefined : 'mt-1.5'}
              value={apiBase}
              onChange={(e) => {
                setApiBase(e.target.value)
              }}
              placeholder={apiBasePlaceholder}
            />
            {defaultApiBase.length > 0 && !baseIsDefault ? (
              <p className="mt-1 text-xs text-muted-foreground">
                该 provider 的默认地址：
                <button
                  type="button"
                  className="ml-1 font-mono text-primary underline-offset-2 hover:underline"
                  onClick={() => {
                    setApiBase(defaultApiBase)
                  }}
                >
                  {defaultApiBase}
                </button>
              </p>
            ) : null}
          </div>
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
