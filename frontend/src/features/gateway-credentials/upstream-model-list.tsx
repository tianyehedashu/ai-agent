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
import { resolveUpstreamModelTypes } from '@/features/gateway-models/infer-model-types'
import { cn } from '@/lib/utils'
import type { ModelType } from '@/types/user-model'
import { MODEL_TYPE_LABELS } from '@/types/user-model'

const TYPE_CHIP_CLASS: Record<ModelType, string> = {
  text: 'border-muted-foreground/30 bg-muted/50 text-[10px] font-normal',
  image: 'border-sky-500/30 bg-sky-500/10 text-[10px] font-normal text-sky-800 dark:text-sky-200',
  image_gen:
    'border-violet-500/30 bg-violet-500/10 text-[10px] font-normal text-violet-800 dark:text-violet-200',
  video:
    'border-amber-500/30 bg-amber-500/10 text-[10px] font-normal text-amber-800 dark:text-amber-200',
}

function ModelTypeChips({ types }: { types: readonly ModelType[] }): React.JSX.Element | null {
  if (types.length === 0) {
    return (
      <Badge variant="outline" className="text-[10px] font-normal text-muted-foreground">
        不可导入
      </Badge>
    )
  }
  return (
    <span className="flex shrink-0 flex-wrap gap-0.5">
      {types.map((t) => (
        <Badge key={t} variant="outline" className={TYPE_CHIP_CLASS[t]}>
          {MODEL_TYPE_LABELS[t]}
        </Badge>
      ))}
    </span>
  )
}

const UpstreamModelRow = memo(function UpstreamModelRow({
  item,
  provider,
  checked,
  onToggle,
  onPickModelId,
}: {
  item: CredentialUpstreamItem
  provider: string
  checked: boolean
  onToggle: (id: string) => void
  onPickModelId?: (id: string) => void
}): React.JSX.Element {
  const importable = isImportableUpstreamItem(item, provider)
  const regLabel = registeredLabel(item)
  const types = resolveUpstreamModelTypes(item, provider)

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
      <ModelTypeChips types={types} />
      {regLabel ? (
        <Badge
          variant="outline"
          className="max-w-[35%] shrink border-amber-500/40 bg-amber-500/10 text-[10px] font-normal text-amber-900 dark:text-amber-200"
        >
          {regLabel}
        </Badge>
      ) : item.owned_by ? (
        <span
          className="max-w-[30%] shrink-0 truncate text-xs text-muted-foreground"
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
  provider: string
  selected: Set<string>
  onToggle: (id: string) => void
  onPickModelId?: (id: string) => void
  isStale?: boolean
  importableCount: number
  allImportableSelected: boolean
  someImportableSelected: boolean
  onToggleAllImportable: () => void
}

export function UpstreamModelList({
  items,
  provider,
  selected,
  onToggle,
  onPickModelId,
  isStale = false,
  importableCount,
  allImportableSelected,
  someImportableSelected,
  onToggleAllImportable,
}: UpstreamModelListProps): React.JSX.Element {
  const parentRef = useRef<HTMLDivElement>(null)
  const rowVirtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 36,
    overscan: 8,
  })

  return (
    <div className="overflow-hidden rounded-md border">
      <div className="sticky top-0 z-10 flex items-center gap-2 border-b bg-background/95 px-2 py-1.5 backdrop-blur-sm">
        <Checkbox
          checked={allImportableSelected ? true : someImportableSelected ? 'indeterminate' : false}
          disabled={importableCount === 0}
          onCheckedChange={() => {
            onToggleAllImportable()
          }}
          aria-label="全选可导入项"
        />
        <span className="text-xs text-muted-foreground">全选可导入项（{importableCount}）</span>
      </div>
      <div
        ref={parentRef}
        className={cn(
          'h-72 overflow-y-auto overscroll-y-contain p-2 text-sm',
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
                  provider={provider}
                  checked={selected.has(it.id)}
                  onToggle={onToggle}
                  onPickModelId={onPickModelId}
                />
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
