/**
 * 配额中心：统一展示 platform / upstream / downstream 规则，支持批量设置。
 */

import { lazy, Suspense } from 'react'

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

import { BudgetModelCombobox } from './budget-model-combobox'
import { QuotaCenterTable } from './quota-center-table'
import { LAYER_LABELS } from './quota-rule-utils'
import { useQuotaCenter } from './use-quota-center'

const QuotaBatchDrawer = lazy(async () => {
  const mod = await import('./quota-batch-drawer')
  return { default: mod.QuotaBatchDrawer }
})

export function QuotaCenterWorkspace(): React.JSX.Element {
  const ws = useQuotaCenter()

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold">配额中心</h2>
          <p className="text-sm text-muted-foreground">
            统一管理平台消费护栏、上游厂商额度与下游客户权益；按层级区分，支持批量设置。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            disabled={ws.formDisabled}
            onClick={() => {
              ws.setBatchOpen(true)
            }}
          >
            批量设置
          </Button>
          <GatewayRefreshButton
            isFetching={ws.isRefreshing}
            ariaLabel="刷新配额规则"
            onRefresh={ws.refresh}
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
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
      </div>

      {ws.formDisabled ? (
        <p className="text-sm text-muted-foreground">
          当前为只读模式（Platform Viewer），无法修改配额。
        </p>
      ) : null}

      <QuotaCenterTable
        items={ws.filteredItems}
        isLoading={ws.isLoading}
        selectedId={ws.selectedId}
        formDisabled={ws.formDisabled}
        labelContext={ws.labelContext}
        onSelect={ws.selectRule}
        onDelete={ws.confirmDelete}
      />

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
