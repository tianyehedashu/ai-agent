/**
 * 团队凭据列表空态引导面板（分组列表专用）。
 */

import type React from 'react'

import { Link } from 'react-router-dom'

import { Key, Search } from '@/lib/lucide-icons'

export interface CredentialsEmptyStateProps {
  noCollaborationTeams?: boolean
  hasActiveSearch?: boolean
}

export function CredentialsEmptyState({
  noCollaborationTeams = false,
  hasActiveSearch = false,
}: CredentialsEmptyStateProps): React.JSX.Element {
  if (noCollaborationTeams) {
    return (
      <div className="rounded-lg border border-dashed bg-muted/10 px-6 py-10 text-center">
        <Key className="mx-auto h-8 w-8 text-muted-foreground/60" />
        <h3 className="mt-3 text-base font-semibold">尚无协作团队</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          团队 Tab 仅管理协作团队的共享凭据。个人 BYOK 请前往{' '}
          <Link
            to="/gateway/credentials?tab=personal"
            className="text-primary underline-offset-4 hover:underline"
          >
            个人
          </Link>{' '}
          Tab 配置。
        </p>
      </div>
    )
  }

  if (hasActiveSearch) {
    return (
      <div className="rounded-lg border border-dashed bg-muted/10 px-6 py-10 text-center">
        <Search className="mx-auto h-8 w-8 text-muted-foreground/60" aria-hidden />
        <h3 className="mt-3 text-base font-semibold">没有匹配的团队</h3>
        <p className="mt-1 text-sm text-muted-foreground">请调整团队名称或 slug 筛选条件后重试。</p>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-dashed bg-muted/10 px-6 py-10 text-center">
      <Key className="mx-auto h-8 w-8 text-muted-foreground/60" />
      <h3 className="mt-3 text-base font-semibold">暂无可管理的协作团队</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        加入协作团队并获得管理员权限后，可在此配置团队共享凭据。
      </p>
    </div>
  )
}
