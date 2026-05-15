/**
 * 平台管理员：凭据维度全局调用统计（不含密钥）
 */

import { useMemo, useState } from 'react'

import { useQuery } from '@tanstack/react-query'
import { LineChart } from 'lucide-react'
import { Navigate } from 'react-router-dom'

import { gatewayApi, type PlatformCredentialStat } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'

function coalesceNumber(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value)
    if (Number.isFinite(n)) return n
  }
  return 0
}

const RANGE_DAYS: { value: 1 | 7 | 30; label: string }[] = [
  { value: 1, label: '24 小时' },
  { value: 7, label: '7 天' },
  { value: 30, label: '30 天' },
]

export default function GatewayPlatformStatsPage(): React.JSX.Element {
  const { isPlatformAdmin, isAuthenticated } = useGatewayPermission()
  const [days, setDays] = useState<1 | 7 | 30>(7)

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['gateway', 'admin', 'credential-stats', days],
    queryFn: () => gatewayApi.adminCredentialStats({ days }),
    enabled: isAuthenticated && isPlatformAdmin,
  })

  const sorted = useMemo(() => {
    const rows = data ?? []
    return [...rows].sort((a, b) => b.requests - a.requests)
  }, [data])

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  if (!isPlatformAdmin) {
    return <Navigate to="/gateway/overview" replace />
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <LineChart className="h-6 w-6 text-primary" />
            平台凭据统计
          </h2>
          <p className="text-sm text-muted-foreground">
            全平台按凭据聚合调用量；关联模型数为引用该凭据的 Gateway 注册模型条数。
          </p>
        </div>
        <div className="flex flex-wrap gap-1 rounded-md border bg-background p-0.5">
          {RANGE_DAYS.map((r) => (
            <Button
              key={r.value}
              size="sm"
              variant={days === r.value ? 'default' : 'ghost'}
              className="h-8 px-3 text-xs"
              type="button"
              onClick={() => {
                setDays(r.value)
              }}
            >
              {r.label}
            </Button>
          ))}
        </div>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">凭据列表</CardTitle>
          <CardDescription>仅统计含 credential_id 的调用日志；费用为区间内汇总。</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading && (
            <p className="px-6 py-8 text-center text-sm text-muted-foreground">加载中…</p>
          )}
          {isError && (
            <p className="px-6 py-8 text-center text-sm text-destructive">{error.message}</p>
          )}
          {!isLoading && !isError && sorted.length === 0 && (
            <p className="px-6 py-8 text-center text-sm text-muted-foreground">暂无数据</p>
          )}
          {!isLoading && !isError && sorted.length > 0 && (
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">凭据</th>
                  <th className="px-4 py-2 text-left font-medium">作用域</th>
                  <th className="px-4 py-2 text-right font-medium">注册模型</th>
                  <th className="px-4 py-2 text-right font-medium">请求</th>
                  <th className="px-4 py-2 text-right font-medium">输入 tok</th>
                  <th className="px-4 py-2 text-right font-medium">输出 tok</th>
                  <th className="px-4 py-2 text-right font-medium">费用 USD</th>
                  <th className="px-4 py-2 text-right font-medium">成功 / 失败</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((row: PlatformCredentialStat) => (
                  <tr key={row.credential_id} className="border-b last:border-0 hover:bg-muted/20">
                    <td className="px-4 py-2">
                      <div className="font-medium">{row.name}</div>
                      <div className="text-xs text-muted-foreground">{row.provider}</div>
                      <div className="font-mono text-[10px] text-muted-foreground/80">
                        {row.credential_id}
                      </div>
                    </td>
                    <td className="px-4 py-2 text-xs">
                      {row.scope}
                      {row.scope_id ? (
                        <div className="mt-0.5 font-mono text-[10px] text-muted-foreground">
                          {row.scope_id}
                        </div>
                      ) : null}
                      <div className="mt-0.5 text-muted-foreground">
                        {row.is_active ? '启用' : '停用'}
                      </div>
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">{row.gateway_model_count}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{row.requests}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{row.input_tokens}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{row.output_tokens}</td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {coalesceNumber(row.cost_usd).toFixed(6)}
                    </td>
                    <td className="px-4 py-2 text-right text-xs tabular-nums">
                      {row.success_count} / {row.failure_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
