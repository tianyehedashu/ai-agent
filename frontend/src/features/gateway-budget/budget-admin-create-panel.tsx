import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { ChevronDown, Plus } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

import { TAB_LABELS, type BudgetAdminTab } from './budget-admin-constants'
import { BudgetInlineForm, type BudgetInlineFormProps } from './budget-inline-form'

import type { BudgetFormValues } from './budget-form-utils'

export interface BudgetAdminCreatePanelProps {
  tab: BudgetAdminTab
  createOpen: boolean
  onCreateOpenChange: (open: boolean) => void
  createValues: BudgetFormValues
  onCreateValuesChange: (values: BudgetFormValues) => void
  onSubmit: () => void
  submitLabel: string
  disabled: boolean
  keys: BudgetInlineFormProps['keys']
  members: BudgetInlineFormProps['members']
  modelOptions: string[]
}

export function BudgetAdminCreatePanel({
  tab,
  createOpen,
  onCreateOpenChange,
  createValues,
  onCreateValuesChange,
  onSubmit,
  submitLabel,
  disabled,
  keys,
  members,
  modelOptions,
}: BudgetAdminCreatePanelProps): React.JSX.Element {
  return (
    <Collapsible open={createOpen} onOpenChange={onCreateOpenChange}>
      <CollapsibleTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5">
          <Plus className="h-4 w-4" />
          新建预算
          <ChevronDown className={cn('h-4 w-4 transition-transform', createOpen && 'rotate-180')} />
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
              onChange={onCreateValuesChange}
              onSubmit={onSubmit}
              submitLabel={submitLabel}
              disabled={disabled}
              keys={keys}
              members={members}
              modelOptions={modelOptions}
              fixedTargetKind={tab}
            />
          </CardContent>
        </Card>
      </CollapsibleContent>
    </Collapsible>
  )
}
