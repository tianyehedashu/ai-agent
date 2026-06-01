import { useMemo, useState } from 'react'
import type React from 'react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Check, ChevronsUpDown, Loader2 } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

/** 与调用统计页筛选「全部」取值一致 */
export const GATEWAY_FILTER_ALL = '__all__'

export interface GatewayFilterOption {
  value: string
  label: string
  meta?: string
}

function matchesSearch(option: GatewayFilterOption, query: string): boolean {
  const haystack = [option.label, option.meta, option.value].filter(Boolean).join(' ').toLowerCase()
  return haystack.includes(query)
}

export type GatewayFilterSearchMode = 'client' | 'server'

/** 下拉面板宽度：wide 用于模型/凭据等长文案 */
export type GatewayFilterMenuWidth = 'default' | 'wide'

/** compact 单行截断；multiline 允许多行完整展示（模型 ID 等） */
export type GatewayFilterOptionLayout = 'compact' | 'multiline'

export interface GatewayFilterComboboxProps {
  value: string
  onChange: (value: string) => void
  options: readonly GatewayFilterOption[]
  placeholder?: string
  allLabel?: string
  searchPlaceholder?: string
  loading?: boolean
  disabled?: boolean
  active?: boolean
  className?: string
  contentClassName?: string
  menuWidth?: GatewayFilterMenuWidth
  optionLayout?: GatewayFilterOptionLayout
  id?: string
  onOpenChange?: (open: boolean) => void
  /** client：本地过滤 options；server：由父组件按搜索词请求后端 */
  searchMode?: GatewayFilterSearchMode
  onSearchQueryChange?: (query: string) => void
  remoteSearching?: boolean
  /** server 模式下无结果时的提示（默认「未找到匹配项」） */
  emptyHint?: string
}

export function GatewayFilterCombobox({
  value,
  onChange,
  options,
  placeholder = '全部',
  allLabel = '全部',
  searchPlaceholder = '搜索…',
  loading = false,
  disabled = false,
  active = false,
  className,
  contentClassName,
  menuWidth = 'default',
  optionLayout = 'compact',
  id,
  onOpenChange,
  searchMode = 'client',
  onSearchQueryChange,
  remoteSearching = false,
  emptyHint,
}: Readonly<GatewayFilterComboboxProps>): React.JSX.Element {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')

  const handleOpenChange = (next: boolean): void => {
    setOpen(next)
    if (!next) setSearch('')
    onOpenChange?.(next)
  }

  const optionsByValue = useMemo(
    () => new Map(options.map((option) => [option.value, option])),
    [options]
  )

  const filteredOptions = useMemo(() => {
    if (searchMode === 'server') return options
    const q = search.trim().toLowerCase()
    if (!q) return options
    return options.filter((option) => matchesSearch(option, q))
  }, [options, search, searchMode])

  const isAll = value === GATEWAY_FILTER_ALL
  const selected = isAll ? null : (optionsByValue.get(value) ?? null)
  const triggerLabel = loading ? '加载中…' : isAll ? placeholder : (selected?.label ?? value)

  const pick = (next: string): void => {
    onChange(next)
    handleOpenChange(false)
  }

  const menuPanelClass =
    menuWidth === 'wide'
      ? 'min-w-[min(22rem,calc(100vw-1.5rem))] w-max max-w-[min(36rem,calc(100vw-1.5rem))]'
      : 'min-w-[min(16rem,calc(100vw-1.5rem))] w-max max-w-[min(26rem,calc(100vw-1.5rem))]'

  const optionCountHint =
    filteredOptions.length > 0
      ? `${filteredOptions.length.toString()} 项${search.trim() ? '（已筛选）' : ''}`
      : null

  return (
    <DropdownMenu open={open} onOpenChange={handleOpenChange}>
      <DropdownMenuTrigger asChild>
        <Button
          id={id}
          type="button"
          variant={active ? 'default' : 'outline'}
          role="combobox"
          aria-expanded={open}
          disabled={disabled || loading}
          className={cn(
            'h-9 min-w-[5.5rem] max-w-[12rem] justify-between text-xs font-normal',
            className
          )}
          title={!isAll && !loading ? triggerLabel : undefined}
        >
          <span className="flex min-w-0 items-center gap-2 truncate">
            {loading ? <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin opacity-60" /> : null}
            <span className="truncate">{triggerLabel}</span>
          </span>
          <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 opacity-50" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        className={cn(
          'max-h-[min(24rem,70vh)] overflow-y-auto overflow-x-hidden p-0',
          menuPanelClass,
          contentClassName
        )}
        collisionPadding={12}
      >
        <div className="sticky top-0 z-10 border-b bg-popover p-2">
          <Input
            value={search}
            placeholder={searchPlaceholder}
            className="h-8 text-xs"
            onChange={(event) => {
              const next = event.target.value
              setSearch(next)
              if (searchMode === 'server') onSearchQueryChange?.(next)
            }}
            onKeyDown={(event) => {
              event.stopPropagation()
            }}
          />
        </div>
        <DropdownMenuLabel className="flex items-center justify-between gap-2 px-2 py-1.5 text-xs font-normal text-muted-foreground">
          <span>{placeholder}</span>
          {optionCountHint ? (
            <span className="shrink-0 tabular-nums">{optionCountHint}</span>
          ) : null}
        </DropdownMenuLabel>
        <DropdownMenuItem
          className="text-xs"
          onSelect={() => {
            pick(GATEWAY_FILTER_ALL)
          }}
        >
          <Check
            className={cn('mr-2 h-3.5 w-3.5', isAll ? 'opacity-100' : 'opacity-0')}
            aria-hidden
          />
          {allLabel}
        </DropdownMenuItem>
        {filteredOptions.length > 0 ? <DropdownMenuSeparator /> : null}
        {remoteSearching && filteredOptions.length === 0 ? (
          <div className="flex items-center justify-center gap-2 px-3 py-4 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
            搜索中…
          </div>
        ) : filteredOptions.length === 0 ? (
          <div className="px-3 py-4 text-center text-xs text-muted-foreground">
            {emptyHint ?? '未找到匹配项'}
          </div>
        ) : (
          filteredOptions.map((option) => {
            const checked = value === option.value
            return (
              <DropdownMenuItem
                key={option.value}
                className={cn('text-xs', optionLayout === 'multiline' && 'items-start py-2')}
                onSelect={() => {
                  pick(option.value)
                }}
              >
                <Check
                  className={cn(
                    'mr-2 h-3.5 w-3.5 shrink-0',
                    optionLayout === 'multiline' && 'mt-0.5',
                    checked ? 'opacity-100' : 'opacity-0'
                  )}
                  aria-hidden
                />
                <div
                  className={cn(
                    'min-w-0 flex-1 flex-col gap-0.5',
                    optionLayout === 'multiline' ? 'flex' : 'flex min-w-0'
                  )}
                >
                  <span
                    className={cn(
                      optionLayout === 'multiline' ? 'break-all font-mono leading-snug' : 'truncate'
                    )}
                    title={option.label}
                  >
                    {option.label}
                  </span>
                  {option.meta ? (
                    <span
                      className={cn(
                        'text-[11px] text-muted-foreground',
                        optionLayout === 'multiline' ? 'break-all' : 'truncate'
                      )}
                      title={option.meta}
                    >
                      {option.meta}
                    </span>
                  ) : null}
                </div>
              </DropdownMenuItem>
            )
          })
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
