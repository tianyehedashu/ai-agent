import { memo, useMemo } from 'react'
import type React from 'react'

import { Link } from 'react-router-dom'

import type { VirtualKey } from '@/api/gateway'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { gatewayTeamKeysHref } from '@/features/gateway-teams/gateway-team-paths'
import { resolveTeamLabelFromMap } from '@/features/gateway-teams/gateway-team-resolve-label'
import { useGatewayMemberTeamNameMap } from '@/features/gateway-teams/use-gateway-teams'
import { formatGatewayManagementError } from '@/lib/gateway-api-error'
import { Eye, EyeOff, Loader2 } from '@/lib/lucide-icons'

export const MANUAL_VKEY_SENTINEL = '__manual__'

export interface PlaygroundKeyFieldProps {
  apiKeyId: string
  apiKey: string
  showKey: boolean
  onApiKeyChange: (value: string) => void
  onShowKeyToggle: () => void
  virtualKeys: VirtualKey[]
  selectedKeyId: string | null
  selectedKey: VirtualKey | null
  isLoadingKeys: boolean
  isRevealing: boolean
  revealError: Error | null
  userEdited: boolean
  onSelectKey: (id: string | null) => void
  onUserEditedReset: () => void
  /** 当前 Playground 团队，用于「创建 Key」链接 */
  teamId?: string | null
}

export const PlaygroundKeyField = memo(function PlaygroundKeyField({
  apiKeyId,
  apiKey,
  showKey,
  onApiKeyChange,
  onShowKeyToggle,
  virtualKeys,
  selectedKeyId,
  selectedKey,
  isLoadingKeys,
  isRevealing,
  revealError,
  userEdited: _userEdited,
  onSelectKey,
  onUserEditedReset,
  teamId,
}: Readonly<PlaygroundKeyFieldProps>): React.JSX.Element {
  const teamNameById = useGatewayMemberTeamNameMap()
  const keysCreateHref = useMemo(() => gatewayTeamKeysHref(teamId), [teamId])
  const hasVirtualKeys = virtualKeys.length > 0
  const manualMode =
    !hasVirtualKeys || selectedKeyId === null || (revealError !== null && selectedKey !== null)
  const manualInputId = hasVirtualKeys ? `${apiKeyId}-manual` : apiKeyId

  return (
    <div className="space-y-1.5">
      <Label htmlFor={manualMode ? manualInputId : apiKeyId}>
        虚拟 Key <span className="text-destructive">*</span>
      </Label>

      {hasVirtualKeys ? (
        <Select
          value={selectedKeyId ?? MANUAL_VKEY_SENTINEL}
          onValueChange={(id) => {
            onUserEditedReset()
            onSelectKey(id === MANUAL_VKEY_SENTINEL ? null : id)
          }}
          disabled={isLoadingKeys}
        >
          <SelectTrigger id={apiKeyId} className="w-full" aria-label="选择虚拟 Key">
            <SelectValue placeholder={isLoadingKeys ? '加载中…' : '选择虚拟 Key'} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={MANUAL_VKEY_SENTINEL}>
              <span className="text-muted-foreground">手动粘贴 Key…</span>
            </SelectItem>
            <SelectGroup>
              <SelectLabel>可用 Key（{String(virtualKeys.length)}）</SelectLabel>
              {virtualKeys.map((k) => (
                <SelectItem key={k.id} value={k.id}>
                  <span className="flex w-full min-w-0 items-center gap-2">
                    <span className="truncate text-foreground/90">
                      {k.name}
                      <span className="text-muted-foreground">
                        {' '}
                        · {resolveTeamLabelFromMap(teamNameById, k.team_id)}
                      </span>
                    </span>
                    <span
                      className="shrink-0 font-mono text-xs text-muted-foreground"
                      translate="no"
                    >
                      {k.masked_key}
                    </span>
                  </span>
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      ) : null}

      {manualMode ? (
        <div className="relative">
          <Input
            id={manualInputId}
            value={apiKey}
            onChange={(e) => {
              onApiKeyChange(e.target.value)
            }}
            placeholder={isRevealing ? '正在获取明文…' : 'sk-gw-...'}
            type={showKey ? 'text' : 'password'}
            autoComplete="off"
            spellCheck={false}
            className="pr-10 font-mono"
            translate="no"
            aria-describedby={`${apiKeyId}-hint`}
          />
          <button
            type="button"
            onClick={onShowKeyToggle}
            className="absolute right-2 top-1/2 inline-flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label={showKey ? '隐藏 Key' : '显示 Key'}
          >
            {showKey ? (
              <EyeOff className="h-4 w-4" aria-hidden="true" />
            ) : (
              <Eye className="h-4 w-4" aria-hidden="true" />
            )}
          </button>
        </div>
      ) : null}

      <PlaygroundApiKeyHint
        hintId={`${apiKeyId}-hint`}
        isLoadingKeys={isLoadingKeys}
        isRevealing={isRevealing}
        selectedKey={selectedKey}
        keysCount={virtualKeys.length}
        revealError={revealError}
        teamNameById={teamNameById}
        keysCreateHref={keysCreateHref}
      />
    </div>
  )
})

const PlaygroundApiKeyHint = memo(function PlaygroundApiKeyHint({
  hintId,
  isLoadingKeys,
  isRevealing,
  selectedKey,
  keysCount,
  revealError,
  teamNameById,
  keysCreateHref,
}: Readonly<{
  hintId: string
  isLoadingKeys: boolean
  isRevealing: boolean
  selectedKey: VirtualKey | null
  keysCount: number
  revealError: Error | null
  teamNameById: ReadonlyMap<string, string>
  keysCreateHref: string
}>): React.JSX.Element | null {
  if (isLoadingKeys) {
    return (
      <p id={hintId} className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
        加载中…
      </p>
    )
  }
  if (revealError && selectedKey) {
    return (
      <p id={hintId} className="text-xs text-destructive">
        {formatGatewayManagementError(revealError)}
      </p>
    )
  }
  if (isRevealing && selectedKey) {
    return (
      <p id={hintId} className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
        加载 Key…
      </p>
    )
  }
  if (selectedKey) {
    return (
      <p id={hintId} className="text-xs text-muted-foreground">
        绑定团队：{resolveTeamLabelFromMap(teamNameById, selectedKey.team_id)}
      </p>
    )
  }
  if (keysCount === 0) {
    return (
      <p id={hintId} className="text-xs text-muted-foreground">
        暂无 Key。{' '}
        <Link to={keysCreateHref} className="text-primary underline-offset-4 hover:underline">
          创建
        </Link>
      </p>
    )
  }
  return null
})
