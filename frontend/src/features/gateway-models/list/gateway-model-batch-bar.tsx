import { memo } from 'react'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Loader2, RefreshCw, Trash2 } from '@/lib/lucide-icons'

import type { GatewayModelBatchBarProps } from './types'

export const GatewayModelBatchBar = memo(function GatewayModelBatchBar({
  capabilities,
  selectedCount,
  selectableCount,
  allSelectableSelected,
  someSelectableSelected,
  onToggleSelectAll,
  onBatchTestSelected,
  onBatchResyncSelected,
  onBatchDelete,
  batchBusy = false,
  testingAll = false,
  resyncingAll = false,
}: GatewayModelBatchBarProps): React.JSX.Element | null {
  const mode = capabilities.batchBarMode ?? 'onSelection'
  const visible =
    capabilities.batchSelect === true &&
    (mode === 'whenHasItems' ? selectableCount > 0 : selectedCount > 0)

  if (!visible) return null

  return (
    <div className="flex flex-wrap items-center gap-3 border-b bg-muted/20 px-3 py-2">
      <label className="flex cursor-pointer items-center gap-2 text-sm">
        <Checkbox
          checked={allSelectableSelected ? true : someSelectableSelected ? 'indeterminate' : false}
          disabled={selectableCount === 0 || batchBusy}
          aria-label="全选可删除的模型"
          onCheckedChange={(checked) => {
            onToggleSelectAll(checked === true)
          }}
        />
        <span className="text-muted-foreground">
          全选可删除项{selectableCount > 0 ? `（${String(selectableCount)}）` : ''}
        </span>
      </label>

      <span className="text-sm text-muted-foreground">已选 {selectedCount} 项</span>

      <div className="ml-auto flex flex-wrap items-center gap-1">
        {capabilities.batchTest !== false && onBatchTestSelected ? (
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs"
            disabled={batchBusy || selectedCount === 0}
            onClick={onBatchTestSelected}
          >
            {testingAll ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}
            批量测试
          </Button>
        ) : null}

        {capabilities.batchResync !== false && onBatchResyncSelected ? (
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs"
            disabled={batchBusy || selectedCount === 0}
            onClick={onBatchResyncSelected}
          >
            {resyncingAll ? (
              <Loader2 className="mr-1 h-3 w-3 animate-spin" />
            ) : (
              <RefreshCw className="mr-1 h-3 w-3" />
            )}
            同步能力
          </Button>
        ) : null}

        {capabilities.batchDelete !== false && onBatchDelete ? (
          <Button
            size="sm"
            variant="destructive"
            className="h-7 text-xs"
            disabled={batchBusy || selectedCount === 0}
            onClick={onBatchDelete}
          >
            <Trash2 className="mr-1 h-3 w-3" />
            批量删除
          </Button>
        ) : null}
      </div>
    </div>
  )
})
