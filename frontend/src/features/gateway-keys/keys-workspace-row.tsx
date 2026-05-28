import { memo } from 'react'

import { Link } from 'react-router-dom'

import type { EntitlementPlan, GatewayBudget, VirtualKey } from '@/api/gateway'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { KeyBudgetInline } from '@/features/gateway-budget/key-budget-inline'
import { KeyEntitlementsCell } from '@/features/gateway-keys/key-entitlements-cell'
import { BookOpen, Eye, Trash2 } from '@/lib/lucide-icons'

import type { VirtualKeyRevealTarget } from './virtual-key-reveal-dialog'

export interface KeysWorkspaceRowProps {
  keyRow: VirtualKey
  teamLabel: string
  canManageKeys: boolean
  isSelected: boolean
  showEntitlementsColumn: boolean
  showBudgetsColumn: boolean
  activePlans: EntitlementPlan[]
  entitlementsLoading: boolean
  budgets: GatewayBudget[]
  onToggleSelect: (id: string, checked: boolean) => void
  onReveal: (target: VirtualKeyRevealTarget) => void
  onRevoke: (id: string, name: string, teamId: string) => void
}

export const KeysWorkspaceRow = memo(function KeysWorkspaceRow({
  keyRow: k,
  teamLabel,
  canManageKeys,
  isSelected,
  showEntitlementsColumn,
  showBudgetsColumn,
  activePlans,
  entitlementsLoading,
  budgets,
  onToggleSelect,
  onReveal,
  onRevoke,
}: Readonly<KeysWorkspaceRowProps>): React.JSX.Element {
  return (
    <tr className="border-b last:border-0 hover:bg-muted/20">
      {canManageKeys ? (
        <td className="px-4 py-2">
          {k.is_active ? (
            <Checkbox
              checked={isSelected}
              aria-label={`选择 ${k.name}`}
              onCheckedChange={(checked) => {
                onToggleSelect(k.id, checked === true)
              }}
            />
          ) : null}
        </td>
      ) : null}
      <td className="px-4 py-2 font-medium">{k.name}</td>
      <td className="px-4 py-2">
        <Badge variant="secondary" className="max-w-[12rem] truncate font-normal" title={k.team_id}>
          {teamLabel}
        </Badge>
      </td>
      <td className="px-4 py-2 font-mono text-xs">{k.masked_key}</td>
      <td className="max-w-[12rem] px-4 py-2 text-xs">
        <span className="block truncate" title={k.allowed_models.join(', ') || '全部'}>
          {k.allowed_models.length === 0 ? '全部' : k.allowed_models.join(', ')}
        </span>
      </td>
      <td className="px-4 py-2 text-xs tabular-nums">
        {`${String(k.rpm_limit ?? '∞')} / ${String(k.tpm_limit ?? '∞')}`}
      </td>
      {showEntitlementsColumn ? (
        <td className="px-4 py-2 text-xs">
          <KeyEntitlementsCell activePlans={activePlans} isLoading={entitlementsLoading} />
        </td>
      ) : null}
      {showBudgetsColumn ? (
        <td className="px-4 py-2 text-xs">
          <KeyBudgetInline budgets={budgets} />
        </td>
      ) : null}
      <td className="px-4 py-2 text-xs">
        {k.is_active ? (
          <Badge variant="secondary" className="font-normal">
            可用
          </Badge>
        ) : (
          <span className="text-muted-foreground">已撤销</span>
        )}
      </td>
      <td className="px-4 py-2">
        <div className="flex items-center gap-1">
          {k.is_active ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" className="h-7 w-7" asChild>
                  <Link
                    to={`/gateway/guide?key_id=${k.id}#clients`}
                    aria-label={`${k.name} 调用指南`}
                  >
                    <BookOpen className="h-3.5 w-3.5" />
                  </Link>
                </Button>
              </TooltipTrigger>
              <TooltipContent>使用本 Key 试调（{teamLabel}）</TooltipContent>
            </Tooltip>
          ) : null}
          {canManageKeys && k.is_active ? (
            <>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                aria-label={`查看 ${k.name} 完整 Key`}
                onClick={() => {
                  onReveal({
                    id: k.id,
                    name: k.name,
                    masked_key: k.masked_key,
                    team_id: k.team_id,
                  })
                }}
              >
                <Eye className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => {
                  onRevoke(k.id, k.name, k.team_id)
                }}
              >
                <Trash2 className="h-3.5 w-3.5 text-destructive" />
              </Button>
            </>
          ) : null}
        </div>
      </td>
    </tr>
  )
})
