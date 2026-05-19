/**
 * 统一「新增凭据」弹窗：覆盖 user / team / system 三种作用域。
 *
 * - scope=user → 调用 `POST /gateway/my-credentials`
 * - scope=team/system → 调用 `POST /gateway/credentials`
 *
 * Provider 候选与差异化 extra 字段由 [`provider-schemas.ts`](./provider-schemas.ts) 驱动。
 */

import { useEffect, useMemo, useState } from 'react'
import type React from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
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
import { Eye, EyeOff } from '@/lib/lucide-icons'

import { ExtraFieldsRenderer } from './credential-extra-fields'
import { compactExtra, type CredentialExtraValues } from './credential-extra-utils'
import {
  apiKeyLabelForProvider,
  defaultApiBaseForProvider,
  extraFieldsForProvider,
  getProviderSchema,
  providersForScope,
  type CredentialFormScope,
} from './provider-schemas'

export interface CreateCredentialValues {
  scope: CredentialFormScope
  provider: string
  name: string
  api_key: string
  api_base?: string
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

export function CreateCredentialDialog({
  open,
  onOpenChange,
  allowedScopes,
  defaultScope,
  defaultProvider,
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
  onSubmit: (values: CreateCredentialValues) => void
  submitting?: boolean
}>): React.JSX.Element {
  const fallbackScope: CredentialFormScope = allowedScopes[0] ?? 'user'
  const resolvedDefaultScope: CredentialFormScope =
    defaultScope && allowedScopes.includes(defaultScope) ? defaultScope : fallbackScope

  const [scope, setScope] = useState<CredentialFormScope>(resolvedDefaultScope)
  const [provider, setProvider] = useState<string>('')
  const [name, setName] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [apiBase, setApiBase] = useState('')
  const [apiBaseTouched, setApiBaseTouched] = useState(false)
  const [extra, setExtra] = useState<CredentialExtraValues>({})
  const [showKey, setShowKey] = useState(false)

  const providerOptions = useMemo(() => providersForScope(scope), [scope])
  const schema = useMemo(() => getProviderSchema(provider), [provider])
  const extraFields = useMemo(() => extraFieldsForProvider(provider), [provider])
  const apiKeyLabel = apiKeyLabelForProvider(provider)

  // 打开时重置；按 scope 切换时若当前 provider 不在新 scope 候选中也重置
  useEffect(() => {
    if (!open) return
    const initialScope = resolvedDefaultScope
    const candidates = providersForScope(initialScope)
    const initialProvider =
      defaultProvider && candidates.some((p) => p.id === defaultProvider)
        ? defaultProvider
        : (candidates[0]?.id ?? '')
    setScope(initialScope)
    setProvider(initialProvider)
    setName('')
    setApiKey('')
    setApiBase(defaultApiBaseForProvider(initialProvider))
    setApiBaseTouched(false)
    setExtra({})
    setShowKey(false)
  }, [open, resolvedDefaultScope, defaultProvider])

  useEffect(() => {
    if (!provider) return
    if (!providerOptions.some((p) => p.id === provider)) {
      const next = providerOptions[0]?.id ?? ''
      setProvider(next)
      setApiBase(defaultApiBaseForProvider(next))
      setApiBaseTouched(false)
      setExtra({})
    }
  }, [providerOptions, provider])

  const handleProviderChange = (next: string): void => {
    setProvider(next)
    setExtra({})
    if (!apiBaseTouched) {
      setApiBase(defaultApiBaseForProvider(next))
    }
  }

  const handleApiBaseChange = (next: string): void => {
    setApiBase(next)
    setApiBaseTouched(true)
  }

  const requiredExtraMissing = extraFields.some((f) => f.required && !(extra[f.key] ?? '').trim())
  const apiBaseMissing = (schema?.apiBaseRequired ?? false) && !apiBase.trim()
  const canSubmit =
    !submitting &&
    Boolean(provider) &&
    Boolean(name.trim()) &&
    Boolean(apiKey.trim()) &&
    !apiBaseMissing &&
    !requiredExtraMissing

  const handleSubmit = (): void => {
    if (!canSubmit) return
    const compactedExtra = compactExtra(extra)
    onSubmit({
      scope,
      provider,
      name: name.trim(),
      api_key: apiKey.trim(),
      api_base: apiBase.trim() || undefined,
      extra: Object.keys(compactedExtra).length > 0 ? compactedExtra : undefined,
    })
  }

  const scopeOptions = useMemo(() => buildScopeOptions(allowedScopes), [allowedScopes])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>新增凭据</DialogTitle>
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
                    : '系统凭据对所有团队生效（需平台管理员）'}
              </p>
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

          <div className="space-y-2">
            <Label>
              api_base
              {schema?.apiBaseRequired ? (
                <span className="ml-1 text-destructive">*</span>
              ) : (
                <span className="ml-1 text-[11px] text-muted-foreground">（可选）</span>
              )}
            </Label>
            <Input
              type="url"
              value={apiBase}
              onChange={(e) => {
                handleApiBaseChange(e.target.value)
              }}
              placeholder={schema?.apiBasePlaceholder ?? schema?.defaultApiBase}
            />
            {schema?.defaultApiBase && !apiBaseTouched ? (
              <p className="text-[11px] text-muted-foreground">
                已自动填充该 provider 的默认地址，可按需修改
              </p>
            ) : null}
          </div>

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
