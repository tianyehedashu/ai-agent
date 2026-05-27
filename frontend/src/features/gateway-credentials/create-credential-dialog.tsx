/**
 * 统一「新增凭据」弹窗：覆盖 user / team / system 三种作用域。
 *
 * - scope=user → 调用 `POST /gateway/my-credentials`
 * - scope=team/system → 调用 `POST /gateway/credentials`
 *
 * Provider 候选与差异化 extra 字段由 [`provider-schemas.ts`](./provider-schemas.ts) 驱动。
 */

import { useEffect, useCallback, useMemo, useState } from 'react'
import type React from 'react'

import type { CredentialApiBases } from '@/api/gateway/credentials'
import type { GatewayTeam } from '@/api/gateway/teams'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { GatewayTeamCombobox } from '@/features/gateway-teams/gateway-team-combobox'
import { Eye, EyeOff } from '@/lib/lucide-icons'

import { CredentialApiBasesFields } from './credential-api-bases-fields'
import {
  apiBaseRequiredForProtocols,
  compactApiBasesForSubmit,
  defaultApiBasesForProfile,
  EMPTY_API_BASES_FORM,
  primaryApiBaseFromForm,
  protocolsForProfile,
  type CredentialApiBasesFormState,
} from './credential-api-bases-utils'
import { ExtraFieldsRenderer } from './credential-extra-fields'
import { compactExtra, type CredentialExtraValues } from './credential-extra-utils'
import { useProviderProfilesCatalog } from './hooks/use-provider-profiles-catalog'
import {
  apiKeyLabelForProvider,
  defaultProfileIdForProvider,
  extraFieldsForProvider,
  getProviderSchema,
  getUpstreamProfileSpec,
  profilesForProvider,
  providersForScope,
  type CredentialFormScope,
} from './provider-schemas'

export interface CreateCredentialValues {
  scope: CredentialFormScope
  /** scope=team 时必填：凭据写入的目标团队 */
  teamId?: string
  provider: string
  name: string
  api_key: string
  api_base?: string
  api_bases?: CredentialApiBases
  profile_id?: string
  extra?: Record<string, string>
}

interface ScopeOption {
  value: CredentialFormScope
  label: string
}

function buildScopeOptions(
  allowedScopes: ReadonlyArray<CredentialFormScope>
): readonly ScopeOption[] {
  const labels: Record<CredentialFormScope, string> = {
    user: '个人',
    team: '团队',
    system: '系统',
  }
  return allowedScopes.map((s) => ({ value: s, label: labels[s] }))
}

function resolveInitialTeamId(
  writableTeams: readonly GatewayTeam[],
  defaultTeamId: string | undefined
): string {
  if (defaultTeamId && writableTeams.some((team) => team.id === defaultTeamId)) {
    return defaultTeamId
  }
  return writableTeams[0]?.id ?? ''
}

export function CreateCredentialDialog({
  open,
  onOpenChange,
  allowedScopes,
  defaultScope,
  defaultProvider,
  writableTeams,
  defaultTeamId,
  routeTeamId,
  onSubmit,
  submitting,
}: Readonly<{
  open: boolean
  onOpenChange: (v: boolean) => void
  /** 当前用户在本上下文中允许选择的 scope 集合（至少一个） */
  allowedScopes: ReadonlyArray<CredentialFormScope>
  /** 打开时的默认 scope；若不在 allowedScopes 内则回退到第一个 */
  defaultScope?: CredentialFormScope
  /** 打开时的默认 provider；若不在 scope 候选内则回退到该 scope 的第一项 */
  defaultProvider?: string
  /** scope=team 时可写团队列表（由外层 useGatewayWritableTeams 提供） */
  writableTeams?: readonly GatewayTeam[]
  /** scope=team 时默认选中的团队（通常为路由 teamId） */
  defaultTeamId?: string
  /** 当前路由工作区团队，用于跨团队创建提示 */
  routeTeamId?: string
  onSubmit: (values: CreateCredentialValues) => void
  submitting?: boolean
}>): React.JSX.Element {
  useProviderProfilesCatalog(open)

  const fallbackScope: CredentialFormScope = allowedScopes[0] ?? 'user'
  const resolvedDefaultScope: CredentialFormScope =
    defaultScope && allowedScopes.includes(defaultScope) ? defaultScope : fallbackScope

  const [scope, setScope] = useState<CredentialFormScope>(resolvedDefaultScope)
  const [provider, setProvider] = useState<string>('')
  const [name, setName] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [apiBases, setApiBases] = useState<CredentialApiBasesFormState>(EMPTY_API_BASES_FORM)
  const [apiBasesTouched, setApiBasesTouched] = useState(false)
  const [profileId, setProfileId] = useState('')
  const [extra, setExtra] = useState<CredentialExtraValues>({})
  const [showKey, setShowKey] = useState(false)
  const [teamId, setTeamId] = useState('')

  const teamOptions = useMemo(() => writableTeams ?? [], [writableTeams])

  const providerOptions = useMemo(() => providersForScope(scope), [scope])
  const schema = useMemo(() => getProviderSchema(provider), [provider])
  const profileOptions = useMemo(() => profilesForProvider(provider), [provider])
  const activeProfile = useMemo(
    () => getUpstreamProfileSpec(provider, profileId || undefined),
    [provider, profileId]
  )
  const extraFields = useMemo(() => extraFieldsForProvider(provider), [provider])
  const apiKeyLabel = apiKeyLabelForProvider(provider)

  const profileDefaults = useMemo(
    () => defaultApiBasesForProfile(activeProfile, schema?.defaultApiBase),
    [activeProfile, schema?.defaultApiBase]
  )
  const activeProtocols = useMemo(
    () => protocolsForProfile(activeProfile, schema?.defaultApiBase),
    [activeProfile, schema?.defaultApiBase]
  )
  const apiBaseRequired = useMemo(
    () => apiBaseRequiredForProtocols(activeProtocols, schema?.apiBaseRequired),
    [activeProtocols, schema?.apiBaseRequired]
  )

  // 打开时重置；按 scope 切换时若当前 provider 不在新 scope 候选中也重置
  useEffect(() => {
    if (!open) return
    const initialScope = resolvedDefaultScope
    const candidates = providersForScope(initialScope)
    const initialProvider =
      defaultProvider && candidates.some((p) => p.id === defaultProvider)
        ? defaultProvider
        : (candidates[0]?.id ?? '')
    const initialProfile = defaultProfileIdForProvider(initialProvider) ?? ''
    const initialProfileSpec = getUpstreamProfileSpec(initialProvider, initialProfile || undefined)
    const initialSchema = getProviderSchema(initialProvider)
    setScope(initialScope)
    setProvider(initialProvider)
    setName('')
    setApiKey('')
    setProfileId(initialProfile)
    setApiBases(defaultApiBasesForProfile(initialProfileSpec, initialSchema?.defaultApiBase))
    setApiBasesTouched(false)
    setExtra({})
    setShowKey(false)
    setTeamId(resolveInitialTeamId(teamOptions, defaultTeamId))
  }, [open, resolvedDefaultScope, defaultProvider, defaultTeamId, teamOptions])

  useEffect(() => {
    if (!provider) return
    if (!providerOptions.some((p) => p.id === provider)) {
      const next = providerOptions[0]?.id ?? ''
      const nextProfile = defaultProfileIdForProvider(next) ?? ''
      const nextSpec = getUpstreamProfileSpec(next, nextProfile || undefined)
      const nextSchema = getProviderSchema(next)
      setProvider(next)
      setProfileId(nextProfile)
      setApiBases(defaultApiBasesForProfile(nextSpec, nextSchema?.defaultApiBase))
      setApiBasesTouched(false)
      setExtra({})
    }
  }, [providerOptions, provider])

  useEffect(() => {
    if (scope !== 'team') return
    if (teamId && teamOptions.some((team) => team.id === teamId)) return
    setTeamId(resolveInitialTeamId(teamOptions, defaultTeamId))
  }, [scope, teamId, teamOptions, defaultTeamId])

  const handleProviderChange = (next: string): void => {
    setProvider(next)
    setExtra({})
    const nextProfile = defaultProfileIdForProvider(next) ?? ''
    const nextSpec = getUpstreamProfileSpec(next, nextProfile || undefined)
    const nextSchema = getProviderSchema(next)
    setProfileId(nextProfile)
    if (!apiBasesTouched) {
      setApiBases(defaultApiBasesForProfile(nextSpec, nextSchema?.defaultApiBase))
    }
  }

  const handleProfileChange = (nextProfile: string): void => {
    setProfileId(nextProfile)
    if (!apiBasesTouched) {
      const spec = getUpstreamProfileSpec(provider, nextProfile)
      setApiBases(defaultApiBasesForProfile(spec, schema?.defaultApiBase))
    }
  }

  const handleApiBasesChange = useCallback((next: CredentialApiBasesFormState): void => {
    setApiBases(next)
    setApiBasesTouched(true)
  }, [])

  const requiredExtraMissing = extraFields.some((f) => f.required && !(extra[f.key] ?? '').trim())
  const apiBaseMissing = apiBaseRequired && !primaryApiBaseFromForm(apiBases)
  const teamScopeReady = scope !== 'team' || Boolean(teamId)
  const canSubmit =
    !submitting &&
    Boolean(provider) &&
    Boolean(name.trim()) &&
    Boolean(apiKey.trim()) &&
    !apiBaseMissing &&
    !requiredExtraMissing &&
    teamScopeReady

  const handleSubmit = (): void => {
    if (!canSubmit) return
    const compactedExtra = compactExtra(extra)
    const submittedBases = compactApiBasesForSubmit(apiBases, profileDefaults)
    const openaiBase = apiBases.openai_compat.trim() || undefined
    onSubmit({
      scope,
      teamId: scope === 'team' ? teamId : undefined,
      provider,
      name: name.trim(),
      api_key: apiKey.trim(),
      api_base: openaiBase,
      api_bases: submittedBases,
      profile_id: profileId.trim() || undefined,
      extra: Object.keys(compactedExtra).length > 0 ? compactedExtra : undefined,
    })
  }

  const scopeOptions = useMemo(() => buildScopeOptions(allowedScopes), [allowedScopes])
  const crossTeamTarget = scope === 'team' && routeTeamId && teamId && teamId !== routeTeamId

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>新增凭据</DialogTitle>
          <DialogDescription>
            填写提供商与 API Key，保存后可在模型列表中绑定使用。
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3 py-2">
          {scopeOptions.length > 1 ? (
            <div className="space-y-2">
              <Label>作用域</Label>
              <Select
                value={scope}
                onValueChange={(v) => {
                  setScope(v as CredentialFormScope)
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {scopeOptions.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-[11px] text-muted-foreground">
                {scope === 'user'
                  ? '个人凭据仅当前账号可见，存储于 /my-credentials'
                  : scope === 'team'
                    ? '团队凭据由团队所有成员可见、管理员可写'
                    : '创建后默认对所有团队公开；可在详情中改为「受限」并指定授权团队。'}
              </p>
            </div>
          ) : null}

          {scope === 'team' ? (
            <div className="space-y-2">
              <Label>目标团队</Label>
              <GatewayTeamCombobox
                value={teamId}
                onChange={setTeamId}
                teams={teamOptions}
                disabled={teamOptions.length === 0}
                placeholder={teamOptions.length === 0 ? '无可管理的团队' : '选择团队'}
              />
              {teamOptions.length === 0 ? (
                <p className="text-[11px] text-destructive">当前账号没有可写入团队凭据的团队。</p>
              ) : (
                <>
                  <p className="text-[11px] text-muted-foreground">
                    凭据将写入所选团队，团队成员可见、管理员可写。
                  </p>
                  {crossTeamTarget ? (
                    <p className="text-[11px] text-amber-700 dark:text-amber-400">
                      将创建到其他团队，创建后需切换工作区查看。
                    </p>
                  ) : null}
                </>
              )}
            </div>
          ) : null}

          <div className="space-y-2">
            <Label>提供商</Label>
            <Select value={provider} onValueChange={handleProviderChange}>
              <SelectTrigger>
                <SelectValue placeholder="请选择" />
              </SelectTrigger>
              <SelectContent>
                {providerOptions.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {schema?.helpText ? (
              <p className="text-[11px] text-muted-foreground">{schema.helpText}</p>
            ) : null}
          </div>

          {profileOptions.length > 1 ? (
            <div className="space-y-2">
              <Label>方案</Label>
              <Select value={profileId} onValueChange={handleProfileChange}>
                <SelectTrigger>
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
                <p className="text-[11px] text-muted-foreground">
                  {activeProfile.anthropicDirectHint}
                </p>
              ) : null}
            </div>
          ) : null}

          <div className="space-y-2">
            <Label>名称</Label>
            <Input
              value={name}
              onChange={(e) => {
                setName(e.target.value)
              }}
              placeholder="work / personal / default"
            />
          </div>

          <div className="space-y-2">
            <Label>
              {apiKeyLabel}
              <span className="ml-1 text-destructive">*</span>
            </Label>
            <div className="relative">
              <Input
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => {
                  setApiKey(e.target.value)
                }}
                placeholder={schema?.apiKeyPlaceholder}
                className="pr-10"
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="absolute right-1 top-1/2 h-8 w-8 -translate-y-1/2"
                onClick={() => {
                  setShowKey((v) => !v)
                }}
              >
                {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </Button>
            </div>
            {schema?.apiKeyHelpText ? (
              <p className="text-[11px] text-muted-foreground">{schema.apiKeyHelpText}</p>
            ) : null}
          </div>

          <CredentialApiBasesFields
            idPrefix="create-cred"
            apiBases={apiBases}
            onChange={handleApiBasesChange}
            activeProfile={activeProfile}
            providerDefaultApiBase={schema?.defaultApiBase}
            protocols={activeProtocols}
            apiBaseRequired={apiBaseRequired}
          />

          <ExtraFieldsRenderer
            fields={extraFields}
            values={extra}
            onChange={setExtra}
            idPrefix="create-cred-extra"
          />
        </div>

        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => {
              onOpenChange(false)
            }}
          >
            取消
          </Button>
          <Button onClick={handleSubmit} disabled={!canSubmit}>
            {submitting ? '保存中…' : '创建'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
