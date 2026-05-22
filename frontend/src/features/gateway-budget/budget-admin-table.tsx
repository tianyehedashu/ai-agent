import type { GatewayBudget } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Loader2, Trash2 } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

import {
  computeBudgetUsageMetrics,
  formatBudgetPeriod,
  formatBudgetResetAt,
  formatBudgetTargetKind,
} from './budget-progress-utils'

export interface BudgetAdminTableProps {
  items: GatewayBudget[]
  isLoading: boolean
  selectedId: string | null
  formDisabled: boolean
  onSelect: (budget: GatewayBudget) => void
  onDelete: (budget: GatewayBudget) => void
}

export function BudgetAdminTable({
  items,
  isLoading,
  selectedId,
  formDisabled,
  onSelect,
  onDelete,
}: BudgetAdminTableProps): React.JSX.Element {
  return (
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
            {!isLoading && items.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                  暂无预算
                </td>
              </tr>
            ) : null}
            {items.map((b) => {
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
                    onSelect(b)
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
                      <span className="text-xs tabular-nums">{(ratio * 100).toFixed(1)}%</span>
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
                        onDelete(b)
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
  )
}
