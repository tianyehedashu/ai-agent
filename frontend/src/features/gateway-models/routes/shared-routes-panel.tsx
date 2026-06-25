/**
 * 共享路由面板（消费团队侧）
 *
 * 列出共享进本团队的路由（其他成员的个人路由经委派授权），成员只读可见；
 * 团队 owner/admin 可"移除"（撤销授权）。
 */

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  useEjectSharedRoute,
  useSharedRoutes,
} from '@/features/gateway-models/hooks/use-route-grants'
import { useToast } from '@/hooks/use-toast'
import { Loader2, Route, Trash2 } from '@/lib/lucide-icons'

interface SharedRoutesPanelProps {
  teamId: string
  canManage: boolean
}

export function SharedRoutesPanel({
  teamId,
  canManage,
}: SharedRoutesPanelProps): React.JSX.Element | null {
  const { toast } = useToast()
  const { data: sharedRoutes = [], isLoading } = useSharedRoutes(teamId)
  const ejectMutation = useEjectSharedRoute(teamId)

  if (!isLoading && sharedRoutes.length === 0) return null

  function handleEject(grantId: string, alias: string): void {
    ejectMutation.mutate(grantId, {
      onSuccess: () => {
        toast({ title: `已移除共享路由「${alias}」` })
      },
      onError: (e: Error) => {
        toast({ variant: 'destructive', title: '移除失败', description: e.message })
      },
    })
  }

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Route className="h-4 w-4 text-muted-foreground" />
        共享进本团队的路由
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        其他成员发布给本团队的个人路由，可直接以暴露别名调用；用量计入本团队。
      </p>

      <div className="mt-3">
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        ) : (
          <ul className="divide-y">
            {sharedRoutes.map((shared) => (
              <li key={shared.grant_id} className="flex items-center justify-between gap-3 py-2">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 font-mono text-sm font-medium">
                    <span className="min-w-0 truncate">{shared.exposed_alias}</span>
                    {shared.owner_display ? (
                      <Badge variant="outline" className="shrink-0 font-sans font-normal">
                        {shared.owner_display}
                      </Badge>
                    ) : null}
                  </p>
                  {shared.virtual_model && shared.virtual_model !== shared.exposed_alias ? (
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">
                      源路由 <span className="font-mono">{shared.virtual_model}</span>
                    </p>
                  ) : null}
                </div>
                {canManage ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    className="shrink-0 text-destructive hover:text-destructive"
                    disabled={ejectMutation.isPending}
                    onClick={() => {
                      handleEject(shared.grant_id, shared.exposed_alias)
                    }}
                  >
                    <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                    移除
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
