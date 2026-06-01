/**
 * 配额中心：统一展示 platform / upstream / downstream 规则，支持批量设置。
 */

import { lazy, Suspense, useState } from 'react'

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
import { LAYER_LABELS } from './quota-rule-utils'
import { useQuotaCenter } from './use-quota-center'

const QuotaBatchDrawer = lazy(async () => {
  const mod = await import('./quota-batch-drawer')
  return { default: mod.QuotaBatchDrawer }
})

export function QuotaCenterWorkspace(): React.JSX.Element {
  const ws = useQuotaCenter()
  const [viewMode, setViewMode] = useState<'table' | 'card'>('table')
  const isMember = ws.mode === 'member'

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold">{isMember ? '我的配额' : '配额中心'}</h2>
          <p className="text-sm text-muted-foreground">
            {isMember
              ? '查看与我相关的配额，并为本人在「自己创建的团队凭据」上自助设置消费限额。'
              : '统一管理平台消费护栏、上游厂商额度与下游客户权益；按层级区分，支持批量设置。'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            disabled={ws.formDisabled}
            onClick={() => {
              ws.setBatchOpen(true)
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

      <QuotaOverviewCards rules={ws.filteredItems} isLoading={ws.isLoading} />

      {ws.formDisabled ? (
        <p className="text-sm text-muted-foreground">当前为只读模式，无法修改配额。</p>
      ) : null}
      {isMember && !ws.formDisabled ? (
        <p className="text-xs text-muted-foreground">
          自助配额仅作用于本人在「自己创建的团队凭据」上的消费；个人 BYOK 凭据请在凭据页就地设限。
        </p>
      ) : null}

      {viewMode === 'table' ? (
        <QuotaCenterTable
          items={ws.filteredItems}
          isLoading={ws.isLoading}
          selectedId={ws.selectedId}
          formDisabled={ws.formDisabled}
          labelContext={ws.labelContext}
          onSelect={ws.selectRule}
          onDelete={ws.confirmDelete}
          onBatchDelete={ws.confirmBatchDelete}
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
        />
      )}

      {ws.batchOpen ? (
        <Suspense fallback={null}>
          <QuotaBatchDrawer
            open={ws.batchOpen}
            onOpenChange={ws.setBatchOpen}
            values={ws.batchValues}
            onChange={ws.setBatchValues}
            onSubmit={ws.submitBatch}
            disabled={ws.formDisabled}
            pending={ws.batchPending}
            previewCount={ws.batchPreviewCount}
            mode={ws.mode}
            memberOptions={ws.memberOptions}
            keyOptions={ws.keyOptions}
            credentialOptions={ws.credentialOptions}
            metaLoading={ws.metaLoading}
            modelOptions={ws.modelOptions}
            modelsLoading={ws.modelsLoading}
            onModelPickerOpenChange={ws.onModelPickerOpenChange}
          />
        </Suspense>
      ) : null}
    </div>
  )
}
