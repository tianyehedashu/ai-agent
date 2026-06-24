import { useCallback, useDeferredValue, useMemo, useState } from 'react'

import { ModelStatusBadge } from '@/components/model-status-badge'
import { PaginationControls } from '@/components/pagination-controls'
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
import { CAPABILITIES, capabilityLabel } from '@/features/gateway-models/constants'
import type { RoutePickerModel } from '@/features/gateway-models/routes/use-personal-route-callable-models'
import { useGatewayMemberTeamNameMap } from '@/features/gateway-teams/use-gateway-teams'
import { LayoutGrid } from '@/lib/lucide-icons'

const TEAM_KIND_LABEL: Record<RoutePickerModel['team_kind'], string> = {
  personal: '个人',
  shared: '团队',
  system: '系统',
}

/** 批量弹窗每页条数：在浏览大量跨团队模型时避免长列表渲染卡顿 */
const BATCH_PICKER_PAGE_SIZE = 50

/**
 * 细粒度特性标签：在 capability（聊天/向量/图片生成…）之下进一步区分。
 * 判断依据为 model_types + selector_capabilities（与 ModelCapabilityBadges 对齐）。
 */
interface ModelFeatureTag {
  key: string
  label: string
  test: (model: RoutePickerModel) => boolean
}

const MODEL_FEATURE_TAGS: readonly ModelFeatureTag[] = [
  {
    key: 'vision',
    label: '图片理解',
    test: (m) =>
      (m.model_types ?? []).includes('image') || m.selector_capabilities?.supports_vision === true,
  },
  {
    key: 'tools',
    label: '工具调用',
    test: (m) => m.selector_capabilities?.supports_tools === true,
  },
  {
    key: 'reasoning',
    label: '推理',
    test: (m) => m.selector_capabilities?.supports_reasoning === true,
  },
  {
    key: 'json_mode',
    label: 'JSON 模式',
    test: (m) => m.selector_capabilities?.supports_json_mode === true,
  },
]

/** 判断模型是否具备指定特性 */
function modelHasFeature(model: RoutePickerModel, featureKey: string): boolean {
  const tag = MODEL_FEATURE_TAGS.find((t) => t.key === featureKey)
  return tag ? tag.test(model) : false
}

/** 收集模型具备的所有特性 key（用于列表项 Badge 展示） */
function modelFeatureKeys(model: RoutePickerModel): string[] {
  return MODEL_FEATURE_TAGS.filter((t) => t.test(model)).map((t) => t.key)
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
  const [capabilityFilter, setCapabilityFilter] = useState<string>('all')
  const [featureFilter, setFeatureFilter] = useState<Set<string>>(new Set())
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [page, setPage] = useState(1)

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

  /** 候选中实际出现的能力集合（用于动态渲染能力筛选下拉项） */
  const capabilityChoices = useMemo(() => {
    const caps = new Set<string>()
    for (const item of available) {
      if (item.capability) caps.add(item.capability)
    }
    // 按 CAPABILITIES 已知顺序排序，未知能力排在最后
    const knownOrder = new Map<string, number>(CAPABILITIES.map((cap, idx) => [cap, idx]))
    return [...caps].sort((a, b) => {
      const ia = knownOrder.get(a) ?? Number.MAX_SAFE_INTEGER
      const ib = knownOrder.get(b) ?? Number.MAX_SAFE_INTEGER
      if (ia !== ib) return ia - ib
      return a.localeCompare(b)
    })
  }, [available])

  const filtered = useMemo(() => {
    const requiredFeatures = [...featureFilter]
    return available.filter((item) => {
      if (teamFilter !== 'all') {
        const tid = item.tenant_id ?? item.team_id
        if (teamFilter === 'system') {
          if (item.team_kind !== 'system') return false
        } else if (tid !== teamFilter) {
          return false
        }
      }
      if (capabilityFilter !== 'all' && item.capability !== capabilityFilter) return false
      // 特性筛选：选中的所有特性都必须满足（AND 逻辑）
      if (requiredFeatures.length > 0) {
        for (const fk of requiredFeatures) {
          if (!modelHasFeature(item, fk)) return false
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
  }, [available, deferredSearch, teamFilter, capabilityFilter, featureFilter, teamNameById])

  // 筛选条件变化时回到第一页：渲染期间调整 state，避免 useEffect 引入额外渲染
  // 参考 https://react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes
  const filterKey = `${deferredSearch}\0${teamFilter}\0${capabilityFilter}\0${[...featureFilter].join(',')}`
  const [prevFilterKey, setPrevFilterKey] = useState(filterKey)
  if (filterKey !== prevFilterKey) {
    setPrevFilterKey(filterKey)
    setPage(1)
  }

  const totalFiltered = filtered.length
  const totalPages = Math.max(1, Math.ceil(totalFiltered / BATCH_PICKER_PAGE_SIZE))
  const safePage = Math.min(page, totalPages)
  const pagedFiltered = useMemo(() => {
    const start = (safePage - 1) * BATCH_PICKER_PAGE_SIZE
    return filtered.slice(start, start + BATCH_PICKER_PAGE_SIZE)
  }, [filtered, safePage])

  const allCurrentPageSelected =
    pagedFiltered.length > 0 && pagedFiltered.every((item) => selected.has(item.name))

  const toggleCurrentPage = useCallback((): void => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (allCurrentPageSelected) {
        for (const item of pagedFiltered) next.delete(item.name)
      } else {
        for (const item of pagedFiltered) next.add(item.name)
      }
      return next
    })
  }, [allCurrentPageSelected, pagedFiltered])

  const toggleOne = useCallback((name: string, checked: boolean): void => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (checked) next.add(name)
      else next.delete(name)
      return next
    })
  }, [])

  const toggleFeature = useCallback((featureKey: string): void => {
    setFeatureFilter((prev) => {
      const next = new Set(prev)
      if (next.has(featureKey)) next.delete(featureKey)
      else next.add(featureKey)
      return next
    })
  }, [])

  const handleConfirm = useCallback((): void => {
    onConfirm([...selected])
    setSelected(new Set())
    setSearch('')
    setTeamFilter('all')
    setCapabilityFilter('all')
    setFeatureFilter(new Set())
    setPage(1)
    onOpenChange(false)
  }, [onConfirm, onOpenChange, selected])

  const handleOpenChange = useCallback(
    (next: boolean): void => {
      if (!next) {
        setSelected(new Set())
        setSearch('')
        setTeamFilter('all')
        setCapabilityFilter('all')
        setFeatureFilter(new Set())
        setPage(1)
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
              <Label htmlFor="route-batch-team-filter" className="text-xs">
                归属
              </Label>
              <Select value={teamFilter} onValueChange={setTeamFilter}>
                <SelectTrigger id="route-batch-team-filter" className="h-8">
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
            <div className="w-44 space-y-1">
              <Label htmlFor="route-batch-capability-filter" className="text-xs">
                能力
              </Label>
              <Select value={capabilityFilter} onValueChange={setCapabilityFilter}>
                <SelectTrigger id="route-batch-capability-filter" className="h-8">
                  <SelectValue placeholder="全部" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部</SelectItem>
                  {capabilityChoices.map((cap) => (
                    <SelectItem key={cap} value={cap}>
                      {capabilityLabel(cap)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-muted-foreground">特性</span>
            {MODEL_FEATURE_TAGS.map((tag) => {
              const active = featureFilter.has(tag.key)
              return (
                <Button
                  key={tag.key}
                  type="button"
                  variant={active ? 'default' : 'outline'}
                  size="sm"
                  className="h-6 px-2 text-xs"
                  aria-pressed={active}
                  onClick={() => {
                    toggleFeature(tag.key)
                  }}
                >
                  {tag.label}
                </Button>
              )
            })}
            {featureFilter.size > 0 ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-xs text-muted-foreground"
                onClick={() => {
                  setFeatureFilter(new Set())
                }}
              >
                清除
              </Button>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            <Checkbox
              id="route-batch-select-all"
              checked={allCurrentPageSelected}
              onCheckedChange={() => {
                toggleCurrentPage()
              }}
            />
            <Label htmlFor="route-batch-select-all" className="text-sm font-normal">
              全选当前页（{pagedFiltered.length} 项）
            </Label>
            {selected.size > 0 ? (
              <span className="text-xs text-muted-foreground">
                已选 {selected.size} 项 / 共 {totalFiltered} 项
              </span>
            ) : (
              <span className="text-xs text-muted-foreground">共 {totalFiltered} 项</span>
            )}
          </div>
        </div>

        <ul className="min-h-0 flex-1 divide-y overflow-y-auto px-2 py-1">
          {isLoadingCandidates ? (
            <li className="px-4 py-12 text-center text-sm text-muted-foreground">正在加载模型…</li>
          ) : pagedFiltered.length === 0 ? (
            <li className="px-4 py-12 text-center text-sm text-muted-foreground">无匹配模型</li>
          ) : (
            pagedFiltered.map((item) => {
              const checked = selected.has(item.name)
              const teamLabel =
                item.team_kind === 'system'
                  ? '系统'
                  : (teamNameById.get(item.tenant_id ?? item.team_id ?? '') ??
                    item.team_slug ??
                    TEAM_KIND_LABEL[item.team_kind])
              const featureKeys = modelFeatureKeys(item)
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
                        {item.capability ? (
                          <Badge
                            variant="secondary"
                            className="text-[10px] font-normal text-muted-foreground"
                          >
                            {capabilityLabel(item.capability)}
                          </Badge>
                        ) : null}
                        {featureKeys.map((fk) => {
                          const tag = MODEL_FEATURE_TAGS.find((t) => t.key === fk)
                          return tag ? (
                            <Badge
                              key={fk}
                              variant="outline"
                              className="text-[10px] font-normal text-primary"
                            >
                              {tag.label}
                            </Badge>
                          ) : null
                        })}
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

        {totalFiltered > 0 ? (
          <div className="border-t px-6 py-2">
            <PaginationControls
              page={safePage}
              page_size={BATCH_PICKER_PAGE_SIZE}
              total={totalFiltered}
              has_next={safePage < totalPages}
              has_prev={safePage > 1}
              onPageChange={setPage}
            />
          </div>
        ) : null}

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
    <Button type="button" variant="secondary" size="sm" disabled={disabled} onClick={onClick}>
      <LayoutGrid className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
      批量添加（跨团队）
    </Button>
  )
}
