/**
 * 上游模型虚拟列表（大列表性能优化）。
 */

import { memo, useRef } from 'react'

import { useVirtualizer } from '@tanstack/react-virtual'

import type { CredentialUpstreamItem } from '@/api/gateway'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  isImportableUpstreamItem,
  registeredLabel,
} from '@/features/gateway-credentials/upstream-import-utils'
import { cn } from '@/lib/utils'

const UpstreamModelRow = memo(function UpstreamModelRow({
  item,
  checked,
  onToggle,
  onPickModelId,
}: {
  item: CredentialUpstreamItem
  checked: boolean
  onToggle: (id: string) => void
  onPickModelId?: (id: string) => void
}): React.JSX.Element {
  const importable = isImportableUpstreamItem(item)
  const regLabel = registeredLabel(item)

  return (
    <label
      className={cn(
        'flex w-full items-center gap-2 rounded px-1 py-1',
        importable
          ? 'cursor-pointer hover:bg-muted/60'
          : 'cursor-default border border-dashed border-muted-foreground/25 bg-muted/50'
      )}
    >
      <Checkbox
        checked={checked}
        disabled={!importable}
        onCheckedChange={() => {
          if (importable) onToggle(item.id)
        }}
      />
      <span className="min-w-0 flex-1 truncate font-mono text-xs" title={item.id}>
        {item.id}
      </span>
      {regLabel ? (
        <Badge
          variant="outline"
          className="max-w-[45%] shrink border-amber-500/40 bg-amber-500/10 text-[10px] font-normal text-amber-900 dark:text-amber-200"
        >
          {regLabel}
        </Badge>
      ) : item.owned_by ? (
        <span
          className="max-w-[40%] shrink-0 truncate text-xs text-muted-foreground"
          title={item.owned_by}
        >
          · {item.owned_by}
        </span>
      ) : null}
      {onPickModelId ? (
        <Button
          type="button"
          variant="link"
          className="ml-auto h-7 shrink-0 px-1 text-xs"
          onClick={(e) => {
            e.preventDefault()
            onPickModelId(item.id)
          }}
        >
          填入
        </Button>
      ) : null}
    </label>
  )
})

export interface UpstreamModelListProps {
  items: CredentialUpstreamItem[]
  selected: Set<string>
  onToggle: (id: string) => void
  onPickModelId?: (id: string) => void
  isStale?: boolean
}

export function UpstreamModelList({
  items,
  selected,
  onToggle,
  onPickModelId,
  isStale = false,
}: UpstreamModelListProps): React.JSX.Element {
  const parentRef = useRef<HTMLDivElement>(null)
  const rowVirtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 36,
    overscan: 8,
  })

  return (
    <div
      ref={parentRef}
      className={cn(
        'h-72 overflow-y-auto overscroll-y-contain rounded-md border p-2 text-sm',
        isStale && 'opacity-70'
      )}
    >
      <div
        className="relative w-full"
        style={{ height: `${String(rowVirtualizer.getTotalSize())}px` }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const it = items[virtualRow.index]
          return (
            <div
              key={it.id}
              className="absolute left-0 top-0 w-full"
              style={{ transform: `translateY(${String(virtualRow.start)}px)` }}
            >
              <UpstreamModelRow
                item={it}
                checked={selected.has(it.id)}
                onToggle={onToggle}
                onPickModelId={onPickModelId}
              />
            </div>
          )
        })}
      </div>
    </div>
  )
}
