/**
 * AI Gateway · 注册模型详情（深链）
 */

import { ChevronLeft } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { TeamModelsWorkspace } from '@/features/gateway-models/team/team-models-workspace'

export default function GatewayModelDetailPage(): React.JSX.Element {
  const { modelId } = useParams<{ modelId: string }>()
  const id = modelId ?? ''

  return (
    <ScrollArea className="h-full">
      <div className="space-y-4 p-1">
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
        <TeamModelsWorkspace initialModelId={id || undefined} />
      </div>
    </ScrollArea>
  )
}
