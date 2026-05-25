import { useMemo } from 'react'

import { Link } from 'react-router-dom'

import { useInfiniteGatewayModelPages } from '@/features/gateway-models/hooks/use-infinite-gateway-model-pages'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { Loader2 } from '@/lib/lucide-icons'

import { SystemCallableModelsList } from './system-callable-models-list'

function BrowseFallback(): React.JSX.Element {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />
      加载系统模型…
    </div>
  )
}

export function SystemModelsBrowseWorkspace(): React.JSX.Element {
  const teamId = useGatewayTeamId()

  const { items: requestableItems, isLoading } = useInfiniteGatewayModelPages(
    teamId,
    { registry_scope: 'requestable' },
    { prefetchMode: 'idle' }
  )

  const systemModels = useMemo(
    () => requestableItems.filter((m) => m.registry_kind === 'system'),
    [requestableItems]
  )

  if (isLoading) {
    return <BrowseFallback />
  }

  if (systemModels.length === 0) {
    return (
      <div className="rounded-lg border border-dashed bg-muted/10 p-8 text-center text-sm text-muted-foreground">
        当前工作区暂无可请求的系统模型。请联系平台管理员配置系统供给，或查看{' '}
        <Link to="/gateway/guide" className="text-primary underline-offset-4 hover:underline">
          调用指南
        </Link>
        。
      </div>
    )
  }

  return <SystemCallableModelsList models={systemModels} />
}
