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
import {
  canLinkToCredentialDetail,
  credentialSummaryLabel,
} from '@/features/gateway-credentials/credential-summary-display'
import { NO_CREDENTIAL } from '@/features/gateway-models/constants'
import { credentialDetailHref } from '@/features/gateway-models/paths'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useResolvedGatewayTeamId } from '@/hooks/use-gateway-team-id'

import type {
  PlaygroundCredentialGroups,
  PlaygroundCredentialOption,
} from './playground-credential-options'

const SCOPE_LABELS: Record<'user' | 'team' | 'system', string> = {
  user: '个人',
  team: '团队',
  system: '系统',
}

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
  const teamId = useResolvedGatewayTeamId()
  const { isAdmin, isPlatformAdmin } = useGatewayPermission()
  const showDetailLink = canLinkToCredentialDetail(selectedSummary, isAdmin, isPlatformAdmin)

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
          <CredentialGroup label="个人" items={grouped.personal} />
          <CredentialGroup label="团队" items={grouped.team} />
          <CredentialGroup label="系统" items={grouped.system} />
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
          {showDetailLink && teamId ? (
            <Link
              to={credentialDetailHref(teamId, credentialId)}
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
          可选：先选凭据再缩小模型列表；未选时展示全部可请求模型。
        </p>
      )}
    </div>
  )
}

function CredentialGroup({
  label,
  items,
}: Readonly<{
  label: string
  items: PlaygroundCredentialOption[]
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
      ? SCOPE_LABELS.user
      : scope === 'system'
        ? SCOPE_LABELS.system
        : SCOPE_LABELS.team
  return (
    <Badge variant="outline" className="shrink-0 text-[10px] font-normal">
      {inactive ? '已停用' : label}
    </Badge>
  )
}
