/**
 * 跨 team 虚拟 Key 调用提示（Guide 试调区，单行 + 必要时补充）
 */

import { Link } from 'react-router-dom'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { gatewayTeamKeysHref } from '@/features/gateway-teams/gateway-team-paths'
import { Network } from '@/lib/lucide-icons'

export interface VkeyCrossTeamBannerProps {
  /** 与 multi-grant vkey 判定一致，不依赖 grants API 是否已返回 */
  visible: boolean
  crossTeamCount?: number
  homonymModels?: readonly string[]
  awaitingReveal?: boolean
  proxyModelsError?: string | null
  onRetryProxyModels?: () => void
  keysHrefTeamId?: string | null
}

export function VkeyCrossTeamBanner({
  visible,
  crossTeamCount = 0,
  homonymModels = [],
  awaitingReveal = false,
  proxyModelsError = null,
  onRetryProxyModels,
  keysHrefTeamId = null,
}: Readonly<VkeyCrossTeamBannerProps>): React.JSX.Element | null {
  if (!visible) return null

  const keysHref = gatewayTeamKeysHref(keysHrefTeamId)
  const grantHint =
    crossTeamCount > 0 ? `已授权 ${String(crossTeamCount)} 个工作区。` : '已启用跨工作区调用。'
  const homonymHint =
    homonymModels.length > 0
      ? ` 同名模型（如 ${homonymModels.slice(0, 2).join('、')}${homonymModels.length > 2 ? ' 等' : ''}）须带 slug 前缀。`
      : ''

  return (
    <Alert variant="default" className="border-border/60 bg-muted/20 py-2">
      <Network className="h-4 w-4 text-primary" />
      <AlertDescription className="space-y-1.5 text-xs leading-relaxed text-muted-foreground">
        <p>
          {grantHint}跨工作区请用{' '}
          <code className="rounded bg-muted px-1">team-slug/model-name</code>，无前缀走个人。
          {homonymHint}
          <Link to={keysHref} className="ml-1 text-primary underline-offset-4 hover:underline">
            管理授权
          </Link>
        </p>
        {awaitingReveal ? (
          <p>选择 Key 并完成 reveal 后，模型列表将与 GET /v1/models 一致。</p>
        ) : null}
        {proxyModelsError ? (
          <p className="flex flex-wrap items-center gap-2 text-destructive">
            <span>模型列表加载失败：{proxyModelsError}</span>
            {onRetryProxyModels ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-6 px-2 text-xs"
                onClick={onRetryProxyModels}
              >
                重试
              </Button>
            ) : null}
          </p>
        ) : null}
      </AlertDescription>
    </Alert>
  )
}
