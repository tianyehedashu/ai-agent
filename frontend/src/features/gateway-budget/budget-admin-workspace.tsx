/**
 * Admin 预算配额工作区：Tab 分作用域 + 内联新建/编辑（无 Dialog）。
 */

import { useCallback, useMemo, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import { gatewayApi, type BudgetUpsertBody, type GatewayBudget } from '@/api/gateway'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { ChevronDown, Loader2, Plus, Trash2 } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

import {
  buildBudgetUpsertBody,
  budgetFormValuesFromBudget,
  DEFAULT_BUDGET_FORM_VALUES,
  type BudgetFormValues,
} from './budget-form-utils'
import {
  computeBudgetUsageMetrics,
  formatBudgetPeriod,
  formatBudgetResetAt,
  formatBudgetTargetKind,
} from './budget-progress-utils'
import { gatewayBudgetsQueryKey } from './use-gateway-budgets'

type BudgetAdminTab = GatewayBudget['target_kind']

const TAB_LABELS: Record<BudgetAdminTab, string> = {
  tenant: '团队',
  user: '用户',
  key: '虚拟 Key',
  system: '系统',
}

function parseAdminTab(raw: string | null, showSystem: boolean): BudgetAdminTab {
  if (raw === 'user' || raw === 'key' || raw === 'system') {
    if (raw === 'system' && !showSystem) return 'tenant'
    return raw
  }
  return 'tenant'
}

function BudgetInlineForm({
  values,
  onChange,
  onSubmit,
  onCancel,
  submitLabel,
  disabled,
  keys,
  members,
  modelOptions,
  fixedTargetKind,
}: Readonly<{
  values: BudgetFormValues
  onChange: (next: BudgetFormValues) => void
  onSubmit: () => void
  onCancel?: () => void
  submitLabel: string
  disabled: boolean
  keys: { id: string; label: string }[]
  members: { id: string; label: string }[]
  modelOptions: string[]
  fixedTargetKind?: BudgetAdminTab
}>): React.JSX.Element {
  const targetKind = fixedTargetKind ?? values.target_kind

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {!fixedTargetKind ? (
        <div>
          <Label>作用域</Label>
          <Select
            value={values.target_kind}
            onValueChange={(val: string) => {
              onChange({
                ...values,
                target_kind: val as BudgetFormValues['target_kind'],
                target_id: '',
              })
            }}
            disabled={disabled}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="tenant">团队</SelectItem>
              <SelectItem value="user">用户</SelectItem>
              <SelectItem value="key">虚拟 Key</SelectItem>
              <SelectItem value="system">系统</SelectItem>
            </SelectContent>
          </Select>
        </div>
      ) : null}
      {targetKind === 'user' ? (
        <div className={fixedTargetKind ? 'sm:col-span-2' : undefined}>
          <Label>用户</Label>
          <Select
            value={values.target_id || undefined}
            onValueChange={(val: string) => {
              onChange({ ...values, target_id: val })
            }}
            disabled={disabled}
          >
            <SelectTrigger>
              <SelectValue placeholder="选择团队成员" />
            </SelectTrigger>
            <SelectContent>
              {members.map((m) => (
                <SelectItem key={m.id} value={m.id}>
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}
      {targetKind === 'key' ? (
        <div className={fixedTargetKind ? 'sm:col-span-2' : undefined}>
          <Label>虚拟 Key</Label>
          <Select
            value={values.target_id || undefined}
            onValueChange={(val: string) => {
              onChange({ ...values, target_id: val })
            }}
            disabled={disabled}
          >
            <SelectTrigger>
              <SelectValue placeholder="选择虚拟 Key" />
            </SelectTrigger>
            <SelectContent>
              {keys.map((k) => (
                <SelectItem key={k.id} value={k.id}>
                  {k.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}
      <div>
        <Label>周期</Label>
        <Select
          value={values.period}
          onValueChange={(val: string) => {
            onChange({ ...values, period: val as BudgetFormValues['period'] })
          }}
          disabled={disabled}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="daily">每日</SelectItem>
            <SelectItem value="monthly">每月</SelectItem>
            <SelectItem value="total">总额（不限期滚动）</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="sm:col-span-2">
        <Label>模型（可选）</Label>
        {modelOptions.length > 0 ? (
          <Select
            value={values.model_name || '__all__'}
            onValueChange={(val: string) => {
              onChange({ ...values, model_name: val === '__all__' ? '' : val })
            }}
            disabled={disabled}
          >
            <SelectTrigger>
              <SelectValue placeholder="全模型汇总" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">全模型汇总</SelectItem>
              {modelOptions.map((name) => (
                <SelectItem key={name} value={name}>
                  {name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <Input
            placeholder="与 API 请求中 model 一致；留空表示全模型汇总"
            value={values.model_name}
            onChange={(e) => {
              onChange({ ...values, model_name: e.target.value })
            }}
            disabled={disabled}
          />
        )}
      </div>
      <div>
        <Label>限额 USD（可选）</Label>
        <Input
          type="text"
          inputMode="decimal"
          value={values.limit_usd}
          onChange={(e) => {
            onChange({ ...values, limit_usd: e.target.value })
          }}
          disabled={disabled}
        />
      </div>
      <div>
        <Label>软限额 USD（可选）</Label>
        <Input
          type="text"
          inputMode="decimal"
          value={values.soft_limit_usd}
          onChange={(e) => {
            onChange({ ...values, soft_limit_usd: e.target.value })
          }}
          disabled={disabled}
        />
      </div>
      <div>
        <Label>限额 Token（可选）</Label>
        <Input
          type="text"
          inputMode="numeric"
          value={values.limit_tokens}
          onChange={(e) => {
            onChange({ ...values, limit_tokens: e.target.value })
          }}
          disabled={disabled}
        />
      </div>
      <div>
        <Label>限额请求数（可选）</Label>
        <Input
          type="text"
          inputMode="numeric"
          value={values.limit_requests}
          onChange={(e) => {
            onChange({ ...values, limit_requests: e.target.value })
          }}
          disabled={disabled}
        />
      </div>
      <div className="flex flex-wrap gap-2 sm:col-span-2">
        <Button type="button" onClick={onSubmit} disabled={disabled}>
          {submitLabel}
        </Button>
        {onCancel ? (
          <Button type="button" variant="ghost" onClick={onCancel} disabled={disabled}>
            取消
          </Button>
        ) : null}
      </div>
    </div>
  )
}

export function BudgetAdminWorkspace(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const { isPlatformAdmin, isPlatformViewer } = useGatewayPermission()
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab = parseAdminTab(searchParams.get('tab'), isPlatformAdmin)
  const modelFilter = searchParams.get('model') ?? ''
  const periodFilter = searchParams.get('period') ?? 'all'
  const [createOpen, setCreateOpen] = useState(false)
  const [createValues, setCreateValues] = useState<BudgetFormValues>({
    ...DEFAULT_BUDGET_FORM_VALUES,
    target_kind: activeTab === 'system' ? 'system' : activeTab,
  })
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [editValues, setEditValues] = useState<BudgetFormValues | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<GatewayBudget | null>(null)

  const formDisabled = isPlatformViewer

  const { data: items, isLoading } = useQuery({
    queryKey: gatewayBudgetsQueryKey(teamId, { target_kind: activeTab }),
    queryFn: () => gatewayApi.listBudgets(teamId, { target_kind: activeTab }),
  })

  const { data: keys = [] } = useQuery({
    queryKey: ['gateway', 'keys', teamId],
    queryFn: () => gatewayApi.listKeys(teamId),
    enabled: activeTab === 'key' || createValues.target_kind === 'key',
  })

  const { data: members = [] } = useQuery({
    queryKey: ['gateway', 'members', teamId],
    queryFn: () => gatewayApi.listMembers(teamId),
    enabled: activeTab === 'user' || createValues.target_kind === 'user',
  })

  const { data: models = [] } = useQuery({
    queryKey: ['gateway', 'models', teamId, 'budget-admin'],
    queryFn: () => gatewayApi.listModels(teamId, { registry_scope: 'team' }),
  })

  const modelOptions = useMemo(
    () => [...new Set(models.map((m) => m.name))].sort((a, b) => a.localeCompare(b)),
    [models]
  )

  const keyOptions = useMemo(
    () =>
      keys
        .filter((k) => !k.is_system)
        .map((k) => ({
          id: k.id,
          label: k.name.trim() ? k.name : k.masked_key,
        })),
    [keys]
  )

  const memberOptions = useMemo(
    () =>
      members.map((m) => ({
        id: m.user_id,
        label: `${m.role} · ${m.user_id.slice(0, 8)}…`,
      })),
    [members]
  )

  const filteredItems = useMemo(() => {
    let rows = items ?? []
    if (modelFilter.trim() !== '') {
      const m = modelFilter.trim()
      rows = rows.filter((b) => b.model_name === m)
    }
    if (periodFilter !== 'all') {
      rows = rows.filter((b) => b.period === periodFilter)
    }
    return rows
  }, [items, modelFilter, periodFilter])

  const selectedBudget = useMemo(
    () => (items ?? []).find((b) => b.id === selectedId) ?? null,
    [items, selectedId]
  )

  const invalidateBudgets = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ['gateway', 'budgets'] })
  }, [queryClient])

  const upsertMutation = useMutation({
    mutationFn: (body: BudgetUpsertBody) => gatewayApi.upsertBudget(teamId, body),
    onSuccess: () => {
      invalidateBudgets()
      toast({ title: '预算已保存' })
      setCreateOpen(false)
      setCreateValues({
        ...DEFAULT_BUDGET_FORM_VALUES,
        target_kind: activeTab === 'system' ? 'system' : activeTab,
      })
      setSelectedId(null)
      setEditValues(null)
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '保存失败', description: e.message })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => gatewayApi.deleteBudget(teamId, id),
    onSuccess: () => {
      invalidateBudgets()
      toast({ title: '已删除' })
      setDeleteTarget(null)
      setSelectedId(null)
      setEditValues(null)
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '删除失败', description: e.message })
    },
  })

  const handleTabChange = (tab: string): void => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('tab', tab)
      return next
    })
    setSelectedId(null)
    setEditValues(null)
    setCreateValues((v) => ({
      ...v,
      target_kind: tab as BudgetFormValues['target_kind'],
      target_id: '',
    }))
  }

  const submitForm = (values: BudgetFormValues): void => {
    const body = buildBudgetUpsertBody(values)
    if (body === null) {
      toast({
        variant: 'destructive',
        title: '请完善表单',
        description: '需选择目标并至少填写一项限额（USD / Token / 请求数）',
      })
      return
    }
    upsertMutation.mutate(body)
  }

  const tabs: BudgetAdminTab[] = isPlatformAdmin
    ? ['tenant', 'user', 'key', 'system']
    : ['tenant', 'user', 'key']

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold">预算配额管理</h2>
        <p className="text-sm text-muted-foreground">
          按团队 / 用户 / 虚拟 Key / 系统设置 Gateway 消费上限；可选单模型计量。
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList>
          {tabs.map((tab) => (
            <TabsTrigger key={tab} value={tab}>
              {TAB_LABELS[tab]}
            </TabsTrigger>
          ))}
        </TabsList>

        {tabs.map((tab) => (
          <TabsContent key={tab} value={tab} className="mt-4 space-y-4">
            <Collapsible open={createOpen} onOpenChange={setCreateOpen}>
              <CollapsibleTrigger asChild>
                <Button variant="outline" size="sm" className="gap-1.5">
                  <Plus className="h-4 w-4" />
                  新建预算
                  <ChevronDown
                    className={cn('h-4 w-4 transition-transform', createOpen && 'rotate-180')}
                  />
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-3">
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">新建 {TAB_LABELS[tab]} 预算</CardTitle>
                    <CardDescription>保存后立即生效；同作用域 + 周期 + 模型唯一。</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <BudgetInlineForm
                      values={{ ...createValues, target_kind: tab }}
                      onChange={setCreateValues}
                      onSubmit={() => {
                        submitForm({ ...createValues, target_kind: tab })
                      }}
                      submitLabel={upsertMutation.isPending ? '保存中…' : '创建'}
                      disabled={formDisabled || upsertMutation.isPending}
                      keys={keyOptions}
                      members={memberOptions}
                      modelOptions={modelOptions}
                      fixedTargetKind={tab}
                    />
                  </CardContent>
                </Card>
              </CollapsibleContent>
            </Collapsible>

            <div className="flex flex-wrap gap-3">
              <div className="min-w-[160px]">
                <Label className="text-xs text-muted-foreground">模型筛选</Label>
                <Select
                  value={modelFilter || '__all__'}
                  onValueChange={(val: string) => {
                    setSearchParams((prev) => {
                      const next = new URLSearchParams(prev)
                      if (val === '__all__') next.delete('model')
                      else next.set('model', val)
                      return next
                    })
                  }}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue placeholder="全部模型" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__all__">全部模型</SelectItem>
                    {modelOptions.map((name) => (
                      <SelectItem key={name} value={name}>
                        {name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="min-w-[140px]">
                <Label className="text-xs text-muted-foreground">周期</Label>
                <Select
                  value={periodFilter}
                  onValueChange={(val: string) => {
                    setSearchParams((prev) => {
                      const next = new URLSearchParams(prev)
                      if (val === 'all') next.delete('period')
                      else next.set('period', val)
                      return next
                    })
                  }}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部周期</SelectItem>
                    <SelectItem value="daily">每日</SelectItem>
                    <SelectItem value="monthly">每月</SelectItem>
                    <SelectItem value="total">总额</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <Card>
              <CardContent className="p-0">
                <table className="w-full text-sm">
                  <thead className="border-b bg-muted/30 text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="px-4 py-2 text-left font-medium">目标</th>
                      <th className="px-4 py-2 text-left font-medium">模型</th>
                      <th className="px-4 py-2 text-left font-medium">周期</th>
                      <th className="px-4 py-2 text-left font-medium">已用 / 限额</th>
                      <th className="px-4 py-2 text-left font-medium">使用率</th>
                      <th className="px-4 py-2 text-left font-medium">下次重置</th>
                      <th className="px-4 py-2 text-left font-medium" />
                    </tr>
                  </thead>
                  <tbody>
                    {isLoading ? (
                      <tr>
                        <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                          <Loader2 className="mx-auto mb-2 h-4 w-4 animate-spin" />
                          加载中…
                        </td>
                      </tr>
                    ) : null}
                    {!isLoading && filteredItems.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                          暂无预算
                        </td>
                      </tr>
                    ) : null}
                    {filteredItems.map((b) => {
                      const { ratio, barColor } = computeBudgetUsageMetrics(b)
                      const limitUsd = b.limit_usd ?? null
                      const limitTok = b.limit_tokens ?? null
                      const isSelected = selectedId === b.id
                      return (
                        <tr
                          key={b.id}
                          className={cn(
                            'cursor-pointer border-b last:border-0 hover:bg-muted/20',
                            isSelected && 'bg-primary/5'
                          )}
                          onClick={() => {
                            setSelectedId(b.id)
                            setEditValues(budgetFormValuesFromBudget(b))
                          }}
                        >
                          <td className="px-4 py-2 text-xs">
                            {formatBudgetTargetKind(b.target_kind)}
                            {b.target_id ? (
                              <span className="block truncate text-muted-foreground">
                                {b.target_id.slice(0, 8)}…
                              </span>
                            ) : null}
                          </td>
                          <td className="max-w-[140px] truncate px-4 py-2 text-xs">
                            {b.model_name ?? '（全模型）'}
                          </td>
                          <td className="px-4 py-2 text-xs">{formatBudgetPeriod(b.period)}</td>
                          <td className="px-4 py-2 text-xs tabular-nums">
                            USD {b.current_usd.toFixed(4)} /{' '}
                            {limitUsd !== null ? `$${limitUsd.toFixed(2)}` : '∞'}
                            <br />
                            Token {b.current_tokens} / {limitTok ?? '∞'}
                          </td>
                          <td className="px-4 py-2">
                            <div className="flex items-center gap-2">
                              <div className="h-2 w-24 overflow-hidden rounded bg-muted">
                                <div
                                  className={`h-full ${barColor}`}
                                  style={{
                                    width: `${Math.min(100, (ratio > 0 ? ratio : 0) * 100).toFixed(1)}%`,
                                  }}
                                />
                              </div>
                              <span className="text-xs tabular-nums">
                                {(ratio * 100).toFixed(1)}%
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-2 text-xs">{formatBudgetResetAt(b)}</td>
                          <td className="px-4 py-2">
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-7 w-7"
                              disabled={formDisabled}
                              onClick={(e) => {
                                e.stopPropagation()
                                setDeleteTarget(b)
                              }}
                            >
                              <Trash2 className="h-3.5 w-3.5 text-destructive" />
                            </Button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </CardContent>
            </Card>

            {selectedBudget && editValues ? (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">编辑预算</CardTitle>
                  <CardDescription>
                    {formatBudgetTargetKind(selectedBudget.target_kind)} ·{' '}
                    {selectedBudget.model_name ?? '全模型'} ·{' '}
                    {formatBudgetPeriod(selectedBudget.period)}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <BudgetInlineForm
                    values={editValues}
                    onChange={setEditValues}
                    onSubmit={() => {
                      submitForm(editValues)
                    }}
                    onCancel={() => {
                      setSelectedId(null)
                      setEditValues(null)
                    }}
                    submitLabel={upsertMutation.isPending ? '保存中…' : '保存更改'}
                    disabled={formDisabled || upsertMutation.isPending}
                    keys={keyOptions}
                    members={memberOptions}
                    modelOptions={modelOptions}
                    fixedTargetKind={tab}
                  />
                </CardContent>
              </Card>
            ) : null}
          </TabsContent>
        ))}
      </Tabs>

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={() => {
          setDeleteTarget(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除预算？</AlertDialogTitle>
            <AlertDialogDescription>
              删除后该作用域下的限额将立即失效，此操作不可撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteMutation.isPending}
              onClick={() => {
                if (deleteTarget) deleteMutation.mutate(deleteTarget.id)
              }}
            >
              {deleteMutation.isPending ? '删除中…' : '删除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
