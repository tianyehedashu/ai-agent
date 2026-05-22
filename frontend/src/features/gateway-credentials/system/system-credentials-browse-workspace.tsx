/**
 * 系统凭据只读浏览：成员通过 summaries API 查看 scope=system（无密钥、无详情深链）。
 */

import { useMemo } from 'react'

import { Link } from 'react-router-dom'

import type { CredentialSummary } from '@/api/gateway'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { providerLabel } from '@/features/gateway-credentials/provider-schemas'
import { useGatewayCredentialDirectory } from '@/features/gateway-credentials/use-credential-directory'
import { systemModelsBrowseIndexHref } from '@/features/gateway-models/paths'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { Loader2 } from '@/lib/lucide-icons'

function BrowseFallback(): React.JSX.Element {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />
      加载系统凭据…
    </div>
  )
}

function SystemCredentialsBrowseTable({
  items,
}: Readonly<{ items: CredentialSummary[] }>): React.JSX.Element {
  return (
    <Card>
      <CardContent className="p-0">
        <ScrollArea className="w-full overscroll-y-contain">
          <table className="w-full min-w-[520px] text-sm">
            <thead className="border-b bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-2 text-left font-medium">名称</th>
                <th className="px-4 py-2 text-left font-medium">提供商</th>
                <th className="px-4 py-2 text-left font-medium">启用</th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id} className="border-b last:border-0 hover:bg-muted/20">
                  <td className="px-4 py-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{c.name}</span>
                      {c.is_config_managed ? (
                        <Badge variant="secondary" className="text-[10px] font-normal">
                          配置同步
                        </Badge>
                      ) : null}
                    </div>
                  </td>
                  <td className="px-4 py-2 text-xs">
                    <div className="flex flex-col">
                      <span className="font-medium">{providerLabel(c.provider)}</span>
                      <span
                        className="font-mono text-[10px] text-muted-foreground"
                        title={c.provider}
                      >
                        {c.provider}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-2 text-xs text-muted-foreground">
                    {c.is_active ? '启用' : '禁用'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}

export function SystemCredentialsBrowseWorkspace(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const { list, isLoading } = useGatewayCredentialDirectory()

  const systemCredentials = useMemo(() => list.filter((c) => c.scope === 'system'), [list])

  if (isLoading) {
    return <BrowseFallback />
  }

  if (systemCredentials.length === 0) {
    return (
      <div className="rounded-lg border border-dashed bg-muted/10 p-8 text-center text-sm text-muted-foreground">
        当前工作区暂无系统凭据。挂载在这些凭据上的模型见{' '}
        <Link
          to={systemModelsBrowseIndexHref(teamId)}
          className="text-primary underline-offset-4 hover:underline"
        >
          系统模型
        </Link>
        ，或查看{' '}
        <Link to="/gateway/guide" className="text-primary underline-offset-4 hover:underline">
          调用指南
        </Link>
        。
      </div>
    )
  }

  return <SystemCredentialsBrowseTable items={systemCredentials} />
}
