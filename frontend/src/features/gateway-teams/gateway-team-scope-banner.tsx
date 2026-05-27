/**
 * Gateway 团队工作区作用域说明（虚拟 Key 等）
 */

import { Link } from 'react-router-dom'

import { gatewayTeamDisplayLabel } from '@/features/gateway-teams/gateway-team-display'
import { useGatewayMemberTeams } from '@/features/gateway-teams/use-gateway-teams'
import { useUserStore } from '@/stores/user'

export type GatewayTeamScopeBannerVariant = 'keys'

export interface GatewayTeamScopeBannerProps {
  teamId: string
  variant: GatewayTeamScopeBannerVariant
}

export function GatewayTeamScopeBanner({
  teamId,
  variant: _variant,
}: Readonly<GatewayTeamScopeBannerProps>): React.JSX.Element {
  const viewerUserId = useUserStore((s) => s.currentUser?.id ?? null)
  const { data: teams = [] } = useGatewayMemberTeams()
  const team = teams.find((t) => t.id === teamId)
  const teamLabel = team
    ? gatewayTeamDisplayLabel(team, { viewerUserId })
    : `${teamId.slice(0, 8)}…`
  const isPersonal = team?.kind === 'personal'
  const modelsHref = `/gateway/teams/${encodeURIComponent(teamId)}/models`

  return (
    <div className="rounded-md border border-border/60 bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
      <p>
        当前团队：<span className="font-medium text-foreground">{teamLabel}</span>
        {isPersonal ? (
          <> · 个人工作区下的虚拟 Key 仅解析本工作区已注册模型</>
        ) : (
          <> · 下列虚拟 Key 创建时绑定本团队，代理调用不会读取 X-Team-Id</>
        )}
      </p>
      <p className="mt-1.5">
        客户端请求中的 <span className="font-mono text-foreground/90">model</span> 须在本团队{' '}
        <Link
          to={modelsHref}
          className="font-medium text-primary underline-offset-4 hover:underline"
        >
          模型管理
        </Link>{' '}
        中注册且凭据可用；与右上角团队切换器保持一致。
      </p>
    </div>
  )
}
