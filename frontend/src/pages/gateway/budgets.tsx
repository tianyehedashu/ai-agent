/**
 * AI Gateway · 预算配额
 */

import { useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'

import { gatewayApi, type BudgetUpsertBody, type GatewayBudget } from '@/api/gateway'
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
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useToast } from '@/hooks/use-toast'

export default function GatewayBudgetsPage(): React.JSX.Element {
  const { isAdmin } = useGatewayPermission()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [open, setOpen] = useState(false)

  const { data: items, isLoading } = useQuery({
    queryKey: ['gateway', 'budgets'],
    queryFn: () => gatewayApi.listBudgets(),
  })

  const createMutation = useMutation({
    mutationFn: gatewayApi.upsertBudget,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'budgets'] })
      toast({ title: '预算已创建' })
      setOpen(false)
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '创建失败', description: e.message })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => gatewayApi.deleteBudget(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'budgets'] })
      toast({ title: '已删除' })
    },
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">预算配额</h2>
          <p className="text-sm text-muted-foreground">按系统/团队/Key/用户四级配额，跨周期生效</p>
        </div>
        {isAdmin && (
          <Button
            size="sm"
            onClick={() => {
              setOpen(true)
            }}
          >
            <Plus className="mr-1.5 h-4 w-4" />
            新增预算
          </Button>
        )}
      </div>

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-2 text-left font-medium">作用域</th>
                <th className="px-4 py-2 text-left font-medium">周期</th>
                <th className="px-4 py-2 text-left font-medium">已用 / 限额</th>
                <th className="px-4 py-2 text-left font-medium">使用率</th>
                <th className="px-4 py-2 text-left font-medium">下次重置</th>
                <th className="px-4 py-2 text-left font-medium" />
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">
                    加载中...
                  </td>
                </tr>
              )}
              {!isLoading && (items?.length ?? 0) === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">
                    暂无预算
                  </td>
                </tr>
              )}
              {items?.map((b: GatewayBudget) => {
                const limit = b.limit_usd ?? 0
                const ratio = limit > 0 ? b.current_usd / limit : 0
                const danger = ratio >= 0.9
                return (
                  <tr key={b.id} className="border-b last:border-0 hover:bg-muted/20">
                    <td className="px-4 py-2 text-xs">{b.scope}</td>
                    <td className="px-4 py-2 text-xs">{b.period}</td>
                    <td className="px-4 py-2 text-xs tabular-nums">
                      ${b.current_usd.toFixed(4)} / {limit ? `$${limit.toFixed(2)}` : '∞'}
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-32 overflow-hidden rounded bg-muted">
                          <div
                            className={'h-full ' + (danger ? 'bg-destructive' : 'bg-primary')}
                            style={{ width: `${Math.min(100, ratio * 100).toFixed(1)}%` }}
                          />
                        </div>
                        <span className="text-xs tabular-nums">{(ratio * 100).toFixed(1)}%</span>
                      </div>
                    </td>
                    <td className="px-4 py-2 text-xs">
                      {b.reset_at ? new Date(b.reset_at).toLocaleDateString() : '—'}
                    </td>
                    <td className="px-4 py-2">
                      {isAdmin && (
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7"
                          onClick={() => {
                            if (confirm('删除该预算?')) deleteMutation.mutate(b.id)
                          }}
                        >
                          <Trash2 className="h-3.5 w-3.5 text-destructive" />
                        </Button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <CreateBudgetDialog
        open={open}
        onOpenChange={setOpen}
        onSubmit={(v: BudgetUpsertBody) => {
          createMutation.mutate(v)
        }}
      />
    </div>
  )
}

interface CreateValues {
  scope: 'team' | 'user' | 'key' | 'system'
  period: 'daily' | 'monthly' | 'total'
  limit_usd: number
}

function CreateBudgetDialog({
  open,
  onOpenChange,
  onSubmit,
}: Readonly<{
  open: boolean
  onOpenChange: (v: boolean) => void
  onSubmit: (v: BudgetUpsertBody) => void
}>): React.JSX.Element {
  const [v, setV] = useState<CreateValues>({
    scope: 'team',
    period: 'monthly',
    limit_usd: 100,
  })
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新增预算</DialogTitle>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3 py-2">
          <div>
            <Label>作用域</Label>
            <Select
              value={v.scope}
              onValueChange={(val: string) => {
                setV({ ...v, scope: val as CreateValues['scope'] })
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="team">团队</SelectItem>
                <SelectItem value="user">用户</SelectItem>
                <SelectItem value="key">虚拟 Key</SelectItem>
                <SelectItem value="system">系统</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>周期</Label>
            <Select
              value={v.period}
              onValueChange={(val: string) => {
                setV({ ...v, period: val as CreateValues['period'] })
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="daily">每日</SelectItem>
                <SelectItem value="monthly">每月</SelectItem>
                <SelectItem value="total">总额</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="col-span-2">
            <Label>限额 USD</Label>
            <Input
              type="number"
              value={v.limit_usd}
              onChange={(e) => {
                setV({ ...v, limit_usd: Number(e.target.value) })
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
              onSubmit({
                scope: v.scope,
                period: v.period,
                limit_usd: v.limit_usd,
              })
            }}
          >
            创建
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
