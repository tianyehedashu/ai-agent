import type { GatewayBudget } from '@/api/gateway'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

import { BudgetInlineForm, type BudgetInlineFormProps } from './budget-inline-form'
import { formatBudgetPeriod, formatBudgetTargetKind } from './budget-progress-utils'

import type { BudgetAdminTab } from './budget-admin-constants'
import type { BudgetFormValues } from './budget-form-utils'

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
  modelOptions: string[]
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
          fixedTargetKind={tab}
        />
      </CardContent>
    </Card>
  )
}
