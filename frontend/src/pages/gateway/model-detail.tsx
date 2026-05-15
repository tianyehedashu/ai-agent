/**
 * AI Gateway · 注册模型详情（深链）
 */

import { Suspense, lazy } from 'react'

import { ChevronLeft, Loader2 } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'

const TeamModelsWorkspace = lazy(() =>
  import('@/features/gateway-models/team/team-models-workspace').then((m) => ({
    default: m.TeamModelsWorkspace,
  }))
)

export default function GatewayModelDetailPage(): React.JSX.Element {
  const { modelId } = useParams<{ modelId: string }>()
  const id = modelId ?? ''

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" className="h-8" asChild>
          <Link to="/gateway/models?tab=team">
            <ChevronLeft className="mr-1 h-4 w-4" />
            全部模型
          </Link>
        </Button>
      </div>
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">模型详情</h2>
        <p className="mt-1 font-mono text-sm text-muted-foreground">{id || '—'}</p>
      </div>
      <Suspense
        fallback={
          <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            加载中…
          </div>
        }
      >
        <TeamModelsWorkspace initialModelId={id || undefined} />
      </Suspense>
    </div>
  )
}
