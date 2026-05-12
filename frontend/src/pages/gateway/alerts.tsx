/**
 * AI Gateway · 告警规则
 */

import { useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'

import { gatewayApi, type AlertRule, type AlertRuleCreateBody } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useToast } from '@/hooks/use-toast'

function formatChannels(ch: Record<string, unknown>): string {
  try {
    return JSON.stringify(ch)
  } catch {
    return ''
  }
}

export default function GatewayAlertsPage(): React.JSX.Element {
  const { canWrite } = useGatewayPermission()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [open, setOpen] = useState(false)
  const { data: items, isLoading } = useQuery({
    queryKey: ['gateway', 'alerts'],
    queryFn: () => gatewayApi.listAlerts(),
  })
  const createMutation = useMutation({
    mutationFn: gatewayApi.createAlert,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'alerts'] })
      setOpen(false)
      toast({ title: '已创建告警规则' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '创建失败', description: e.message })
    },
  })
  const deleteMutation = useMutation({
    mutationFn: (id: string) => gatewayApi.deleteAlert(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'alerts'] })
    },
  })
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">告警规则</h2>
          <p className="text-sm text-muted-foreground">基于错误率/成本/延迟的实时告警</p>
        </div>
        {canWrite && (
          <Button
            size="sm"
            onClick={() => {
              setOpen(true)
            }}
          >
            <Plus className="mr-1.5 h-4 w-4" />
            新建规则
          </Button>
        )}
      </div>

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-2 text-left font-medium">名称</th>
                <th className="px-4 py-2 text-left font-medium">指标</th>
                <th className="px-4 py-2 text-left font-medium">阈值</th>
                <th className="px-4 py-2 text-left font-medium">窗口</th>
                <th className="px-4 py-2 text-left font-medium">渠道</th>
                <th className="px-4 py-2 text-left font-medium">状态</th>
                <th className="px-4 py-2 text-left font-medium" />
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={7} className="px-4 py-6 text-center text-muted-foreground">
                    加载中...
                  </td>
                </tr>
              )}
              {!isLoading && (items?.length ?? 0) === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-6 text-center text-muted-foreground">
                    暂无规则
                  </td>
                </tr>
              )}
              {items?.map((r: AlertRule) => (
                <tr key={r.id} className="border-b last:border-0 hover:bg-muted/20">
                  <td className="px-4 py-2">{r.name}</td>
                  <td className="px-4 py-2 font-mono text-xs">{r.metric}</td>
                  <td className="px-4 py-2 text-xs tabular-nums">{r.threshold}</td>
                  <td className="px-4 py-2 text-xs">{r.window_minutes} 分钟</td>
                  <td className="max-w-[140px] truncate px-4 py-2 font-mono text-[11px]">
                    {formatChannels(r.channels)}
                  </td>
                  <td className="px-4 py-2 text-xs">{r.enabled ? '启用' : '禁用'}</td>
                  <td className="px-4 py-2">
                    {canWrite && (
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7"
                        onClick={() => {
                          if (confirm(`删除 ${r.name}?`)) deleteMutation.mutate(r.id)
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5 text-destructive" />
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <CreateAlertDialog
        open={open}
        onOpenChange={setOpen}
        onSubmit={(v) => {
          createMutation.mutate(v)
        }}
      />
    </div>
  )
}

function CreateAlertDialog({
  open,
  onOpenChange,
  onSubmit,
}: Readonly<{
  open: boolean
  onOpenChange: (v: boolean) => void
  onSubmit: (v: AlertRuleCreateBody) => void
}>): React.JSX.Element {
  const [v, setV] = useState({
    name: '',
    metric: 'error_rate' as AlertRuleCreateBody['metric'],
    threshold: 0.1,
    window_minutes: 5,
    webhook_url: '',
    enabled: true,
  })
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建告警规则</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div>
            <Label>名称</Label>
            <Input
              value={v.name}
              onChange={(e) => {
                setV({ ...v, name: e.target.value })
              }}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>指标</Label>
              <Select
                value={v.metric}
                onValueChange={(val) => {
                  setV({ ...v, metric: val as AlertRuleCreateBody['metric'] })
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="error_rate">错误率</SelectItem>
                  <SelectItem value="budget_usage">预算占用</SelectItem>
                  <SelectItem value="latency_p95">延迟 P95</SelectItem>
                  <SelectItem value="request_rate">请求速率</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>阈值</Label>
              <Input
                type="number"
                value={v.threshold}
                onChange={(e) => {
                  setV({ ...v, threshold: Number(e.target.value) })
                }}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>窗口(分钟)</Label>
              <Input
                type="number"
                value={v.window_minutes}
                onChange={(e) => {
                  setV({ ...v, window_minutes: Number(e.target.value) })
                }}
              />
            </div>
            <div>
              <Label>Webhook URL（可选）</Label>
              <Input
                value={v.webhook_url}
                onChange={(e) => {
                  setV({ ...v, webhook_url: e.target.value })
                }}
              />
            </div>
          </div>
          <div className="flex items-center justify-between rounded-md border px-3 py-2">
            <Label htmlFor="alert-enabled" className="cursor-pointer">
              创建后启用
            </Label>
            <Switch
              id="alert-enabled"
              checked={v.enabled}
              onCheckedChange={(checked) => {
                setV({ ...v, enabled: checked })
              }}
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => {
              onOpenChange(false)
            }}
          >
            取消
          </Button>
          <Button
            onClick={() => {
              if (!v.name) return
              const channels: Record<string, unknown> = { inbox: true }
              if (v.webhook_url.trim()) {
                channels.webhook_url = v.webhook_url.trim()
              }
              onSubmit({
                name: v.name,
                metric: v.metric,
                threshold: v.threshold,
                window_minutes: v.window_minutes,
                channels,
                enabled: v.enabled,
              })
            }}
            disabled={!v.name}
          >
            创建
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
