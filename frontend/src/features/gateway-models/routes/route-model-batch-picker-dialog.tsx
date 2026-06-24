import { useCallback, useDeferredValue, useMemo, useState } from 'react'

import { ModelStatusBadge } from '@/components/model-status-badge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { RoutePickerModel } from '@/features/gateway-models/routes/use-personal-route-callable-models'
import { useGatewayMemberTeamNameMap } from '@/features/gateway-teams/use-gateway-teams'
import { LayoutGrid } from '@/lib/lucide-icons'

const TEAM_KIND_LABEL: Record<RoutePickerModel['team_kind'], string> = {
  personal: '个人',
  shared: '团队',
  system: '系统',
}

export interface RouteModelBatchPickerDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  candidates: readonly RoutePickerModel[]
  excludeNames?: readonly string[]
  onConfirm: (routeRefs: string[]) => void
  isLoadingCandidates?: boolean
}

export function RouteModelBatchPickerDialog({
  open,
  onOpenChange,
  candidates,
  excludeNames = [],
  onConfirm,
  isLoadingCandidates = false,
}: RouteModelBatchPickerDialogProps): React.JSX.Element {
  const teamNameById = useGatewayMemberTeamNameMap()
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search.trim().toLowerCase())
  const [teamFilter, setTeamFilter] = useState<string>('all')
  const [selected, setSelected] = useState<Set<string>>(new Set())

  const exclude = useMemo(() => new Set(excludeNames), [excludeNames])

  const available = useMemo(
    () => candidates.filter((item) => item.prefix_dispatchable && !exclude.has(item.name)),
    [candidates, exclude]
  )

  const teamFilterChoices = useMemo(() => {
    const ids = new Set<string>()
    for (const item of available) {
      const tid = item.tenant_id ?? item.team_id
      if (tid) ids.add(tid)
    }
    return [...ids]
  }, [available])

  const filtered = useMemo(() => {
    return available.filter((item) => {
      if (teamFilter !== 'all') {
        const tid = item.tenant_id ?? item.team_id
        if (teamFilter === 'system') {
          if (item.team_kind !== 'system') return false
        } else if (tid !== teamFilter) {
          return false
        }
      }
      if (!deferredSearch) return true
      const haystack = [
        item.name,
        item.registry_name,
        item.provider,
        item.real_model,
        item.team_slug ?? '',
        teamNameById.get(item.tenant_id ?? item.team_id ?? '') ?? '',
      ]
        .join(' ')
        .toLowerCase()
      return haystack.includes(deferredSearch)
    })
  }, [available, deferredSearch, teamFilter, teamNameById])

  const allFilteredSelected =
    filtered.length > 0 && filtered.every((item) => selected.has(item.name))

  const toggleAllFiltered = useCallback((): void => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (allFilteredSelected) {
        for (const item of filtered) next.delete(item.name)
      } else {
        for (const item of filtered) next.add(item.name)
      }
      return next
    })
  }, [allFilteredSelected, filtered])

  const toggleOne = useCallback((name: string, checked: boolean): void => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (checked) next.add(name)
      else next.delete(name)
      return next
    })
  }, [])

  const handleConfirm = useCallback((): void => {
    onConfirm([...selected])
    setSelected(new Set())
    setSearch('')
    setTeamFilter('all')
    onOpenChange(false)
  }, [onConfirm, onOpenChange, selected])

  const handleOpenChange = useCallback(
    (next: boolean): void => {
      if (!next) {
        setSelected(new Set())
        setSearch('')
        setTeamFilter('all')
      }
      onOpenChange(next)
    },
    [onOpenChange]
  )

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="flex max-h-[min(85vh,720px)] max-w-2xl flex-col gap-0 p-0">
        <DialogHeader className="border-b px-6 py-4">
          <DialogTitle className="flex items-center gap-2">
            <LayoutGrid className="h-4 w-4" aria-hidden="true" />
            批量添加模型
          </DialogTitle>
          <DialogDescription>
            从个人、协作团队与系统 callable 模型中多选，添加到主模型池。
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 border-b px-6 py-3">
          <div className="flex flex-wrap gap-3">
            <div className="min-w-[12rem] flex-1 space-y-1">
              <Label htmlFor="route-batch-search" className="text-xs">
                搜索
              </Label>
              <Input
                id="route-batch-search"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value)
                }}
                placeholder="别名、通道、团队…"
                className="h-8"
              />
            </div>
            <div className="w-40 space-y-1">
              <Label className="text-xs">归属</Label>
              <Select value={teamFilter} onValueChange={setTeamFilter}>
                <SelectTrigger className="h-8">
                  <SelectValue placeholder="全部" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部</SelectItem>
                  <SelectItem value="system">系统</SelectItem>
                  {teamFilterChoices.map((teamId) => (
                    <SelectItem key={teamId} value={teamId}>
                      {teamNameById.get(teamId) ?? teamId.slice(0, 8)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox
              id="route-batch-select-all"
              checked={allFilteredSelected}
              onCheckedChange={() => {
                toggleAllFiltered()
              }}
            />
            <Label htmlFor="route-batch-select-all" className="text-sm font-normal">
              全选当前筛选（{filtered.length} 项）
            </Label>
            {selected.size > 0 ? (
              <span className="text-xs text-muted-foreground">已选 {selected.size} 项</span>
            ) : null}
          </div>
        </div>

        <ul className="min-h-0 flex-1 divide-y overflow-y-auto px-2 py-1">
          {isLoadingCandidates ? (
            <li className="px-4 py-12 text-center text-sm text-muted-foreground">正在加载模型…</li>
          ) : filtered.length === 0 ? (
            <li className="px-4 py-12 text-center text-sm text-muted-foreground">无匹配模型</li>
          ) : (
            filtered.map((item) => {
              const checked = selected.has(item.name)
              const teamLabel =
                item.team_kind === 'system'
                  ? '系统'
                  : (teamNameById.get(item.tenant_id ?? item.team_id ?? '') ??
                    item.team_slug ??
                    TEAM_KIND_LABEL[item.team_kind])
              return (
                <li key={item.id}>
                  <label className="flex cursor-pointer items-start gap-3 rounded-md px-3 py-2 hover:bg-muted/40">
                    <Checkbox
                      checked={checked}
                      className="mt-0.5"
                      onCheckedChange={(value) => {
                        toggleOne(item.name, value === true)
                      }}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-sm">{item.name}</span>
                        <Badge variant="outline" className="text-[10px] font-normal">
                          {teamLabel}
                        </Badge>
                        <ModelStatusBadge
                          status={item.last_test_status}
                          testedAt={item.last_tested_at}
                        />
                      </span>
                      {item.registry_name !== item.name ? (
                        <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                          注册名 {item.registry_name} · {item.provider}/{item.real_model}
                        </span>
                      ) : (
                        <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                          {item.provider}/{item.real_model}
                        </span>
                      )}
                    </span>
                  </label>
                </li>
              )
            })
          )}
        </ul>

        <DialogFooter className="border-t px-6 py-4">
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              handleOpenChange(false)
            }}
          >
            取消
          </Button>
          <Tooltip>
            <TooltipTrigger asChild>
              <span>
                <Button type="button" disabled={selected.size === 0} onClick={handleConfirm}>
                  添加 {selected.size > 0 ? selected.size : ''} 个到主模型池
                </Button>
              </span>
            </TooltipTrigger>
            {selected.size === 0 ? <TooltipContent>请先选择至少一个模型</TooltipContent> : null}
          </Tooltip>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function RouteModelBatchAddButton({
  disabled,
  onClick,
}: {
  disabled?: boolean
  onClick: () => void
}): React.JSX.Element {
  return (
    <Button type="button" variant="outline" size="sm" disabled={disabled} onClick={onClick}>
      <LayoutGrid className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
      批量添加
    </Button>
  )
}
