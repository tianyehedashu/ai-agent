import type React from 'react'

import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
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
import { credentialProviderLabel } from '@/features/gateway-credentials/constants'
import { CREDENTIAL_SCOPE_LABELS } from '@/features/gateway-credentials/credential-scope-labels'
import {
  canLinkToCredentialDetail,
  credentialSummaryLabel,
} from '@/features/gateway-credentials/credential-summary-display'
import { NO_CREDENTIAL } from '@/features/gateway-models/constants'
import { credentialDetailHref } from '@/features/gateway-models/paths'
import { useGatewayMemberTeamNameMap } from '@/features/gateway-teams/use-gateway-teams'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayWorkspaceTeamId } from '@/hooks/use-gateway-team-id'
import { useCurrentUser } from '@/stores/user'

import type {
  PlaygroundCredentialGroups,
  PlaygroundCredentialOption,
} from './playground-credential-options'

export interface PlaygroundCredentialFieldProps {
  credentialSelectId: string
  credentialId: string
  onCredentialChange: (id: string) => void
  grouped: PlaygroundCredentialGroups
  selectedSummary: PlaygroundCredentialOption | undefined
  isLoading: boolean
  isEmpty: boolean
}

export function PlaygroundCredentialField({
  credentialSelectId,
  credentialId,
  onCredentialChange,
  grouped,
  selectedSummary,
  isLoading,
  isEmpty,
}: Readonly<PlaygroundCredentialFieldProps>): React.JSX.Element {
  const workspaceTeamId = useGatewayWorkspaceTeamId()
  const teamNameById = useGatewayMemberTeamNameMap()
  const detailTeamId = selectedSummary?.context_team_id ?? workspaceTeamId
  const { canWrite, isPlatformAdmin } = useGatewayPermission()
  const viewerUserId = useCurrentUser()?.id ?? null
  const showDetailLink = canLinkToCredentialDetail(
    selectedSummary,
    viewerUserId,
    canWrite,
    isPlatformAdmin
  )

  const handleValueChange = (value: string): void => {
    onCredentialChange(value === NO_CREDENTIAL ? '' : value)
  }

  return (
    <div className="space-y-1.5">
      <Label htmlFor={credentialSelectId}>凭据</Label>
      <Select value={credentialId || NO_CREDENTIAL} onValueChange={handleValueChange}>
        <SelectTrigger id={credentialSelectId}>
          <SelectValue placeholder={isLoading ? '加载中…' : '全部凭据'} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={NO_CREDENTIAL}>全部凭据</SelectItem>
          <CredentialGroup label="个人" items={grouped.personal} teamNameById={teamNameById} />
          <CredentialGroup label="团队" items={grouped.team} teamNameById={teamNameById} />
          <CredentialGroup label="系统" items={grouped.system} teamNameById={teamNameById} />
        </SelectContent>
      </Select>
      {isLoading ? (
        <p className="text-xs text-muted-foreground">加载凭据目录…</p>
      ) : isEmpty ? (
        <p className="text-xs text-muted-foreground">
          暂无可用凭据。请先到{' '}
          <Link
            to="/gateway/credentials"
            className="text-primary underline-offset-4 hover:underline"
          >
            凭据管理
          </Link>{' '}
          添加并启用。
        </p>
      ) : credentialId && selectedSummary ? (
        <p className="text-xs text-muted-foreground">
          已筛选：
          {showDetailLink && detailTeamId ? (
            <Link
              to={credentialDetailHref(detailTeamId, credentialId)}
              className="ml-1 text-primary underline-offset-4 hover:underline"
            >
              {credentialSummaryLabel(selectedSummary, credentialId)}
            </Link>
          ) : (
            <span className="ml-1">{credentialSummaryLabel(selectedSummary, credentialId)}</span>
          )}
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">
          可选：先选凭据再缩小模型列表；未选凭据时可使用各团队虚拟 Key，选团队/系统凭据后 Key
          与模型会切到对应团队。
        </p>
      )}
    </div>
  )
}

function CredentialGroup({
  label,
  items,
  teamNameById,
}: Readonly<{
  label: string
  items: PlaygroundCredentialOption[]
  teamNameById: ReadonlyMap<string, string>
}>): React.JSX.Element | null {
  if (items.length === 0) return null
  return (
    <SelectGroup>
      <SelectLabel>{label}</SelectLabel>
      {items.map((item) => (
        <SelectItem key={item.id} value={item.id}>
          <span className="flex w-full items-center justify-between gap-2">
            <span className="min-w-0 truncate">
              {item.name}
              <span className="text-muted-foreground">
                {' '}
                · {credentialProviderLabel(item.provider)}
                {item.scope !== 'user' && item.context_team_id
                  ? ` · ${teamNameById.get(item.context_team_id) ?? item.context_team_id.slice(0, 8)}`
                  : ''}
              </span>
            </span>
            <ScopeBadge scope={item.scope} inactive={!item.is_active} />
          </span>
        </SelectItem>
      ))}
    </SelectGroup>
  )
}

function ScopeBadge({
  scope,
  inactive,
}: Readonly<{
  scope: PlaygroundCredentialOption['scope']
  inactive: boolean
}>): React.JSX.Element {
  const label =
    scope === 'user'
      ? CREDENTIAL_SCOPE_LABELS.user
      : scope === 'system'
        ? CREDENTIAL_SCOPE_LABELS.system
        : CREDENTIAL_SCOPE_LABELS.team
  return (
    <Badge variant="outline" className="shrink-0 text-[10px] font-normal">
      {inactive ? '已停用' : label}
    </Badge>
  )
}
