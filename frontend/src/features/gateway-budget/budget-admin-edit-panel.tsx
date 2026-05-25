import type { GatewayBudget } from '@/api/gateway'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

import { BudgetInlineForm, type BudgetInlineFormProps } from './budget-inline-form'
import { formatBudgetPeriod, formatBudgetTargetKind } from './budget-progress-utils'

import type { BudgetAdminTab } from './budget-admin-constants'
import type { BudgetFormValues } from './budget-form-utils'
import type { BudgetModelOption } from './budget-model-options'

export interface BudgetAdminEditPanelProps {
  budget: GatewayBudget
  tab: BudgetAdminTab
  editValues: BudgetFormValues
  onEditValuesChange: (values: BudgetFormValues) => void
  onSubmit: () => void
  onCancel: () => void
  submitLabel: string
  disabled: boolean
  keys: BudgetInlineFormProps['keys']
  members: BudgetInlineFormProps['members']
  modelOptions: BudgetModelOption[]
  modelsLoading?: boolean
  onModelPickerOpenChange?: (open: boolean) => void
}

export function BudgetAdminEditPanel({
  budget,
  tab,
  editValues,
  onEditValuesChange,
  onSubmit,
  onCancel,
  submitLabel,
  disabled,
  keys,
  members,
  modelOptions,
  modelsLoading = false,
  onModelPickerOpenChange,
}: BudgetAdminEditPanelProps): React.JSX.Element {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">编辑预算</CardTitle>
        <CardDescription>
          {formatBudgetTargetKind(budget.target_kind)} · {budget.model_name ?? '全模型'} ·{' '}
          {formatBudgetPeriod(budget.period)}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <BudgetInlineForm
          values={editValues}
          onChange={onEditValuesChange}
          onSubmit={onSubmit}
          onCancel={onCancel}
          submitLabel={submitLabel}
          disabled={disabled}
          keys={keys}
          members={members}
          modelOptions={modelOptions}
          modelsLoading={modelsLoading}
          onModelPickerOpenChange={onModelPickerOpenChange}
          fixedTargetKind={tab}
        />
      </CardContent>
    </Card>
  )
}
