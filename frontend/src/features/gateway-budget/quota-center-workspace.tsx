/**
 * 配额中心：统一展示 platform / upstream / downstream 规则，支持批量设置。
 */

import { lazy, Suspense, useState } from 'react'

import type { QuotaRule } from '@/api/gateway/quota-rules'
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
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { LayoutGrid, List } from '@/lib/lucide-icons'

import { BudgetModelCombobox } from './budget-model-combobox'
import { QuotaCardGrid } from './quota-card-grid'
import { QuotaCenterTable } from './quota-center-table'
import { QuotaOverviewCards } from './quota-overview-cards'
import { isQuotaRuleDeletable } from './quota-rule-delete'
import { LAYER_LABELS } from './quota-rule-utils'
import { useQuotaCenter } from './use-quota-center'

const QuotaBatchWizard = lazy(async () => {
  const mod = await import('./quota-batch-wizard')
  return { default: mod.QuotaBatchWizard }
})

export function QuotaCenterWorkspace(): React.JSX.Element {
  const ws = useQuotaCenter()
  const [viewMode, setViewMode] = useState<'table' | 'card'>('table')
  const isMember = ws.mode === 'member'

  // P11: 删除确认对话框状态
  const [deleteTarget, setDeleteTarget] = useState<QuotaRule | null>(null)
  const [batchDeleteTargets, setBatchDeleteTargets] = useState<QuotaRule[] | null>(null)

  const handleDelete = (rule: QuotaRule): void => {
    if (!isQuotaRuleDeletable(rule)) return
    setDeleteTarget(rule)
  }

  const handleBatchDelete = (rules: QuotaRule[]): void => {
    const deletable = rules.filter(isQuotaRuleDeletable)
    if (deletable.length === 0) return
    setBatchDeleteTargets(deletable)
  }

  const confirmDeleteAction = (): void => {
    if (deleteTarget) {
      ws.confirmDelete(deleteTarget)
      setDeleteTarget(null)
    }
  }

  const confirmBatchDeleteAction = async (): Promise<void> => {
    if (batchDeleteTargets) {
      await ws.confirmBatchDelete(batchDeleteTargets)
      setBatchDeleteTargets(null)
    }
  }

  // 向导模式：batchOpen 时显示向导，否则显示列表
  if (ws.batchOpen) {
    return (
      <Suspense
        fallback={
          <div className="flex items-center justify-center py-12 text-muted-foreground">
            加载中…
          </div>
        }
      >
        <QuotaBatchWizard
          values={ws.batchValues}
          onChange={ws.setBatchValues}
          onSubmit={ws.submitBatch}
          onBack={() => {
            ws.setBatchOpen(false)
          }}
          onDelete={ws.editingRuleId ? ws.deleteEditingRule : undefined}
          disabled={ws.formDisabled}
          pending={ws.batchPending}
          previewCount={ws.batchPreviewCount}
          mode={ws.mode}
          teamName={ws.teamName}
          memberOptions={ws.memberOptions}
          keyOptions={ws.keyOptions}
          credentialOptions={ws.credentialOptions}
          metaLoading={ws.metaLoading}
          modelOptions={ws.batchModelOptions}
          modelsLoading={ws.batchModelsLoading}
          modelOptionMetaLabel={ws.batchModelOptionMetaLabel}
          onModelPickerOpenChange={ws.onModelPickerOpenChange}
          editingRuleId={ws.editingRuleId}
          editingRule={ws.editingRule}
          teamId={ws.teamId}
          labelContext={ws.labelContext}
          upstreamModelAliasByReal={ws.upstreamModelAliasByReal}
          upstreamRealModelsByCredential={ws.upstreamRealModelsByCredential}
        />
      </Suspense>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold">{isMember ? '我的配额' : '配额中心'}</h2>
          <p className="text-sm text-muted-foreground">
            {isMember
              ? '查看与我相关的配额，并为可用凭据自助设置消费限额。'
              : '统一管理平台消费护栏、上游厂商额度与下游客户权益；按层级区分，支持批量设置。'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            disabled={ws.formDisabled}
            onClick={() => {
              ws.openBatchCreate()
            }}
          >
            {isMember ? '设置我的配额' : '批量设置'}
          </Button>
          <GatewayRefreshButton
            isFetching={ws.isRefreshing}
            ariaLabel="刷新配额规则"
            onRefresh={ws.refresh}
          />
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-[140px]">
          <Label className="text-xs text-muted-foreground">层级</Label>
          <Select
            value={ws.layerFilter}
            onValueChange={(v) => {
              ws.setFilter('layer', v)
            }}
          >
            <SelectTrigger className="h-9">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部层级</SelectItem>
              {(['platform', 'upstream', 'downstream'] as const).map((layer) => (
                <SelectItem key={layer} value={layer}>
                  {LAYER_LABELS[layer]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="min-w-[200px]">
          <Label className="text-xs text-muted-foreground">模型筛选</Label>
          <BudgetModelCombobox
            value={ws.modelFilter}
            onChange={(name) => {
              ws.setFilter('model', name)
            }}
            options={ws.modelOptions}
            loading={ws.modelsLoading}
            placeholder="全部模型"
            className="h-9"
            onPopoverOpenChange={ws.onModelPickerOpenChange}
          />
        </div>
        <div className="min-w-[140px]">
          <Label className="text-xs text-muted-foreground">周期</Label>
          <Select
            value={ws.periodFilter}
            onValueChange={(v) => {
              ws.setFilter('period', v)
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

        <div className="ml-auto flex items-center gap-1 rounded-md border bg-background p-0.5">
          <Button
            size="sm"
            variant={viewMode === 'table' ? 'default' : 'ghost'}
            className="h-7 gap-1 px-2 text-xs"
            onClick={() => {
              setViewMode('table')
            }}
          >
            <List className="h-3.5 w-3.5" />
            表格
          </Button>
          <Button
            size="sm"
            variant={viewMode === 'card' ? 'default' : 'ghost'}
            className="h-7 gap-1 px-2 text-xs"
            onClick={() => {
              setViewMode('card')
            }}
          >
            <LayoutGrid className="h-3.5 w-3.5" />
            卡片
          </Button>
        </div>
      </div>

      <QuotaOverviewCards rules={ws.filteredItems} isLoading={ws.isLoading} mode={ws.mode} />

      {ws.listLoadError ? (
        <p className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          配额列表加载失败：{ws.listLoadError}（请刷新或检查后端是否已更新部署）
        </p>
      ) : null}

      {ws.formDisabled ? (
        <p className="text-sm text-muted-foreground">当前为只读模式，无法修改配额。</p>
      ) : null}
      {isMember && !ws.formDisabled ? (
        <p className="text-xs text-muted-foreground">
          自助配额约束您本人在所选凭据上的消费；个人 BYOK 凭据请在凭据页就地设限。
        </p>
      ) : null}

      {viewMode === 'table' ? (
        <QuotaCenterTable
          items={ws.filteredItems}
          isLoading={ws.isLoading}
          selectedId={ws.selectedId}
          formDisabled={ws.formDisabled}
          teamId={ws.teamId}
          mode={ws.mode}
          labelContext={ws.labelContext}
          onSelect={ws.selectRule}
          onEdit={ws.onEditRule}
          onAddFromRule={ws.onAddFromRule}
          canAddFromRule={ws.canAddFromRule}
          onCreate={ws.openBatchCreate}
          onDelete={handleDelete}
          onBatchDelete={handleBatchDelete}
        />
      ) : (
        <QuotaCardGrid
          items={ws.filteredItems}
          isLoading={ws.isLoading}
          selectedId={ws.selectedId}
          labelContext={ws.labelContext}
          viewMode={viewMode}
          onViewModeChange={setViewMode}
          onSelect={ws.selectRule}
          onEdit={ws.onEditRule}
          onAddFromRule={ws.onAddFromRule}
          canAddFromRule={ws.canAddFromRule}
          onCreate={ws.openBatchCreate}
          onDelete={handleDelete}
          formDisabled={ws.formDisabled}
        />
      )}

      {/* P11: 删除确认对话框 */}
      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除配额规则？</AlertDialogTitle>
            <AlertDialogDescription>
              此操作不可撤销。删除后该配额规则将立即失效，相关消费将不再受此限额约束。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDeleteAction}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              确认删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={batchDeleteTargets !== null}
        onOpenChange={(open) => {
          if (!open) setBatchDeleteTargets(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              确认批量删除 {batchDeleteTargets?.length ?? 0} 条配额规则？
            </AlertDialogTitle>
            <AlertDialogDescription>
              此操作不可撤销。删除后所选配额规则将立即失效，相关消费将不再受此限额约束。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmBatchDeleteAction}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              确认删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
