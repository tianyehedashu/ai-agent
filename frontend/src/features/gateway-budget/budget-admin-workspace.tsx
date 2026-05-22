/**
 * Admin 预算配额工作区：Tab 分作用域 + 内联新建/编辑（无 Dialog）。
 */

import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

import { TAB_LABELS } from './budget-admin-constants'
import { BudgetAdminCreatePanel } from './budget-admin-create-panel'
import { BudgetAdminDeleteDialog } from './budget-admin-delete-dialog'
import { BudgetAdminEditPanel } from './budget-admin-edit-panel'
import { BudgetAdminTable } from './budget-admin-table'
import { useBudgetAdminWorkspace } from './use-budget-admin-workspace'

export function BudgetAdminWorkspace(): React.JSX.Element {
  const ws = useBudgetAdminWorkspace()

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold">预算配额管理</h2>
        <p className="text-sm text-muted-foreground">
          按团队 / 用户 / 虚拟 Key / 系统设置 Gateway 消费上限；可选单模型计量。
        </p>
      </div>

      <Tabs value={ws.activeTab} onValueChange={ws.handleTabChange}>
        <TabsList>
          {ws.tabs.map((tab) => (
            <TabsTrigger key={tab} value={tab}>
              {TAB_LABELS[tab]}
            </TabsTrigger>
          ))}
        </TabsList>

        {ws.tabs.map((tab) => (
          <TabsContent key={tab} value={tab} className="mt-4 space-y-4">
            <BudgetAdminCreatePanel
              tab={tab}
              createOpen={ws.createOpen}
              onCreateOpenChange={ws.setCreateOpen}
              createValues={ws.createValues}
              onCreateValuesChange={ws.setCreateValues}
              onSubmit={() => {
                ws.submitForm({ ...ws.createValues, target_kind: tab })
              }}
              submitLabel={ws.upsertPending ? '保存中…' : '创建'}
              disabled={ws.formDisabled || ws.upsertPending}
              keys={ws.keyOptions}
              members={ws.memberOptions}
              modelOptions={ws.modelOptions}
            />

            <div className="flex flex-wrap gap-3">
              <div className="min-w-[160px]">
                <Label className="text-xs text-muted-foreground">模型筛选</Label>
                <Select
                  value={ws.modelFilter || '__all__'}
                  onValueChange={ws.handleModelFilterChange}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue placeholder="全部模型" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__all__">全部模型</SelectItem>
                    {ws.modelOptions.map((name) => (
                      <SelectItem key={name} value={name}>
                        {name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="min-w-[140px]">
                <Label className="text-xs text-muted-foreground">周期</Label>
                <Select value={ws.periodFilter} onValueChange={ws.handlePeriodFilterChange}>
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

            <BudgetAdminTable
              items={ws.filteredItems}
              isLoading={ws.isLoading}
              selectedId={ws.selectedBudget?.id ?? null}
              formDisabled={ws.formDisabled}
              onSelect={ws.selectBudget}
              onDelete={ws.setDeleteTarget}
            />

            {ws.selectedBudget && ws.editValues ? (
              <BudgetAdminEditPanel
                budget={ws.selectedBudget}
                tab={tab}
                editValues={ws.editValues}
                onEditValuesChange={ws.setEditValues}
                onSubmit={() => {
                  const values = ws.editValues
                  if (values) ws.submitForm(values)
                }}
                onCancel={ws.clearSelection}
                submitLabel={ws.upsertPending ? '保存中…' : '保存更改'}
                disabled={ws.formDisabled || ws.upsertPending}
                keys={ws.keyOptions}
                members={ws.memberOptions}
                modelOptions={ws.modelOptions}
              />
            ) : null}
          </TabsContent>
        ))}
      </Tabs>

      <BudgetAdminDeleteDialog
        target={ws.deleteTarget}
        isPending={ws.deletePending}
        onOpenChange={(open) => {
          if (!open) ws.setDeleteTarget(null)
        }}
        onConfirm={ws.confirmDelete}
      />
    </div>
  )
}
