import { memo } from 'react'

import { Link } from 'react-router-dom'

import type { EntitlementPlan, GatewayBudget, VirtualKey } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { KeysWorkspaceRow } from '@/features/gateway-keys/keys-workspace-row'
import { resolveTeamLabelFromMap } from '@/features/gateway-teams/gateway-team-resolve-label'
import { Plus } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

import type { VirtualKeyRevealTarget } from './virtual-key-reveal-dialog'

export interface KeysWorkspaceTableProps {
  teamDisplayName: string
  teamNameById: ReadonlyMap<string, string>
  modelsHref: string
  canManageKeys: boolean
  isLoading: boolean
  isFetching: boolean
  visibleKeys: VirtualKey[]
  showEntitlementsColumn: boolean
  showBudgetsColumn: boolean
  columnCount: number
  allSelectableSelected: boolean
  someSelectableSelected: boolean
  selectedIds: Set<string>
  activeByVkeyId: Map<string, EntitlementPlan[]>
  isLoadingByVkeyId: Map<string, boolean>
  budgetsByKeyId: Map<string, GatewayBudget[]>
  onToggleSelectAll: (checked: boolean) => void
  onToggleSelect: (id: string, checked: boolean) => void
  onReveal: (target: VirtualKeyRevealTarget) => void
  onRevoke: (id: string, name: string) => void
  onCreateClick: () => void
}

export const KeysWorkspaceTable = memo(function KeysWorkspaceTable({
  teamDisplayName,
  teamNameById,
  modelsHref,
  canManageKeys,
  isLoading,
  isFetching,
  visibleKeys,
  showEntitlementsColumn,
  showBudgetsColumn,
  columnCount,
  allSelectableSelected,
  someSelectableSelected,
  selectedIds,
  activeByVkeyId,
  isLoadingByVkeyId,
  budgetsByKeyId,
  onToggleSelectAll,
  onToggleSelect,
  onReveal,
  onRevoke,
  onCreateClick,
}: Readonly<KeysWorkspaceTableProps>): React.JSX.Element {
  return (
    <Card className={cn(isFetching && !isLoading && 'opacity-60 transition-opacity')}>
      <CardContent className="p-0">
        {!isLoading && visibleKeys.length === 0 ? (
          <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
            <p className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground">{teamDisplayName}</span> 下尚无你的虚拟
              Key
            </p>
            {canManageKeys ? (
              <Button size="sm" onClick={onCreateClick}>
                <Plus className="mr-1.5 h-4 w-4" />
                新建虚拟 Key
              </Button>
            ) : null}
            <Link
              to={modelsHref}
              className="text-sm text-primary underline-offset-4 hover:underline"
            >
              前往模型管理
            </Link>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                {canManageKeys ? (
                  <th className="w-10 px-4 py-2 text-left font-medium">
                    <Checkbox
                      checked={
                        allSelectableSelected
                          ? true
                          : someSelectableSelected
                            ? 'indeterminate'
                            : false
                      }
                      disabled={visibleKeys.length === 0}
                      aria-label="全选可用虚拟 Key"
                      onCheckedChange={(checked) => {
                        onToggleSelectAll(checked === true)
                      }}
                    />
                  </th>
                ) : null}
                <th className="px-4 py-2 text-left font-medium">名称</th>
                <th className="px-4 py-2 text-left font-medium">所属团队</th>
                <th className="px-4 py-2 text-left font-medium">Key</th>
                <th className="px-4 py-2 text-left font-medium">允许模型</th>
                <th className="px-4 py-2 text-left font-medium">RPM / TPM</th>
                {showEntitlementsColumn ? (
                  <th className="px-4 py-2 text-left font-medium">客户套餐</th>
                ) : null}
                {showBudgetsColumn ? (
                  <th className="px-4 py-2 text-left font-medium">平台预算</th>
                ) : null}
                <th className="px-4 py-2 text-left font-medium">状态</th>
                <th className="px-4 py-2 text-left font-medium" />
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={columnCount} className="px-4 py-6 text-center text-muted-foreground">
                    加载中…
                  </td>
                </tr>
              ) : null}
              {visibleKeys.map((k) => (
                <KeysWorkspaceRow
                  key={k.id}
                  keyRow={k}
                  teamLabel={resolveTeamLabelFromMap(teamNameById, k.team_id)}
                  teamDisplayName={teamDisplayName}
                  canManageKeys={canManageKeys}
                  isSelected={selectedIds.has(k.id)}
                  showEntitlementsColumn={showEntitlementsColumn}
                  showBudgetsColumn={showBudgetsColumn}
                  activePlans={activeByVkeyId.get(k.id) ?? []}
                  entitlementsLoading={isLoadingByVkeyId.get(k.id) ?? false}
                  budgets={budgetsByKeyId.get(k.id) ?? []}
                  onToggleSelect={onToggleSelect}
                  onReveal={onReveal}
                  onRevoke={onRevoke}
                />
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  )
})
