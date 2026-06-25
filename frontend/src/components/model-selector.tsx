/**
 * ModelSelector - 通用模型选择器
 *
 * 显示系统预置模型 + 用户自定义模型，支持按类型过滤与分页加载。
 */

import { useCallback, useEffect, useMemo, useState } from 'react'

import { useInfiniteQuery } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { GATEWAY_MODELS_AVAILABLE_QUERY_KEY } from '@/features/gateway-models/query-keys'
import { Cpu, Loader2, User } from '@/lib/lucide-icons'
import { PROVIDER_CHANNEL_FILTER_HINT_LONG } from '@/lib/provider-channel-hint'
import { chatReadinessLabel } from '@/pages/chat/components/chat-gateway-setup-alert'
import type { ModelType, SystemModel, UserModel } from '@/types/user-model'
import { MODEL_PROVIDERS } from '@/types/user-model'

const CHANNEL_ALL = '__all__'
const SELECTOR_PAGE_SIZE = 50

export type ModelListMode = 'chat' | 'image_gen' | 'video'

type SelectorModel = (SystemModel | UserModel) & {
  last_test_status?: 'success' | 'failed' | null
  entitlement_status?: 'active' | 'exhausted' | 'resetting' | 'expired' | 'none'
  enabled?: boolean
}

interface ModelSelectorProps {
  modelType?: ModelType
  listMode?: ModelListMode
  /** Gateway 工作区团队（与 POST /chat gateway_team_id 一致） */
  gatewayTeamId?: string | null
  value?: string | null
  onChange: (modelId: string | null) => void
  placeholder?: string
  disabled?: boolean
  className?: string
  showProviderFilter?: boolean
}

function isSelectableModel(model: SelectorModel): boolean {
  const active = model.enabled ?? ('is_active' in model ? model.is_active : true)
  if (!active) return false
  if (model.last_test_status === 'failed') return false
  const entitlement = model.entitlement_status
  if (entitlement === 'exhausted' || entitlement === 'expired') return false
  return true
}

export function ModelSelector({
  modelType,
  listMode,
  gatewayTeamId,
  value,
  onChange,
  placeholder = '默认模型',
  disabled = false,
  className,
  showProviderFilter = false,
}: ModelSelectorProps): React.JSX.Element {
  const [channel, setChannel] = useState<string>(CHANNEL_ALL)
  const [selectOpen, setSelectOpen] = useState(false)

  const providerForApi = showProviderFilter && channel !== CHANNEL_ALL ? channel : undefined
  /** 传入 gatewayTeamId 时等待 personal 工作区就绪，避免无 team 的首轮请求 */
  const modelsQueryEnabled = gatewayTeamId === undefined || gatewayTeamId !== null
  const waitingForTeam = gatewayTeamId === null

  const { data, isLoading, isError, refetch, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useInfiniteQuery({
      queryKey: [
        ...GATEWAY_MODELS_AVAILABLE_QUERY_KEY,
        modelType,
        listMode ?? '',
        showProviderFilter ? channel : '',
        gatewayTeamId ?? '',
      ],
      queryFn: ({ pageParam }) =>
        gatewayApi.listAvailableModels(modelType, providerForApi, {
          ...(listMode ? { mode: listMode } : {}),
          ...(gatewayTeamId ? { gatewayTeamId } : {}),
          page: pageParam,
          page_size: SELECTOR_PAGE_SIZE,
        }),
      initialPageParam: 1,
      getNextPageParam: (lastPage) => {
        if (lastPage.system_models.has_next || lastPage.user_models.has_next) {
          return lastPage.system_models.page + 1
        }
        return undefined
      },
      staleTime: 30_000,
      retry: 1,
      enabled: modelsQueryEnabled,
    })

  const showLoading = isLoading || waitingForTeam

  // 仅在下拉打开时继续翻页，避免 mount 时拉全量
  useEffect(() => {
    if (!selectOpen || !hasNextPage || isFetchingNextPage) return
    void fetchNextPage()
  }, [selectOpen, hasNextPage, isFetchingNextPage, fetchNextPage, data?.pages.length])

  const systemModels = useMemo(
    () => data?.pages.flatMap((page) => page.system_models.items) ?? [],
    [data]
  )
  const userModels = useMemo(
    () => data?.pages.flatMap((page) => page.user_models.items) ?? [],
    [data]
  )
  const systemModelRows = useMemo(
    () =>
      systemModels.map((m) => {
        const unavailable = !isSelectableModel(m as SelectorModel)
        return {
          model: m,
          unavailable,
          sharedRoute: Boolean(m.is_shared_route),
        }
      }),
    [systemModels]
  )
  const userModelRows = useMemo(
    () =>
      userModels.map((m) => ({
        model: m,
        unavailable: !isSelectableModel(m as SelectorModel),
      })),
    [userModels]
  )
  const defaultPage = data?.pages[0]

  const selectableIds = useMemo(() => {
    const ids = new Set<string>()
    for (const { model, unavailable } of systemModelRows) {
      if (!unavailable) ids.add(model.id)
    }
    for (const { model, unavailable } of userModelRows) {
      if (!unavailable) ids.add(model.id)
    }
    return ids
  }, [systemModelRows, userModelRows])

  const hasModels = systemModels.length > 0 || userModels.length > 0

  // 当前选中项可能在后续页：先翻页再找，全量加载完仍不存在才清空
  useEffect(() => {
    if (value === null || value === undefined || isLoading || isError) return
    if (selectableIds.has(value)) return
    if (hasNextPage || isFetchingNextPage) {
      if (hasNextPage && !isFetchingNextPage) {
        void fetchNextPage()
      }
      return
    }
    onChange(null)
  }, [
    value,
    selectableIds,
    isLoading,
    isError,
    hasNextPage,
    isFetchingNextPage,
    fetchNextPage,
    onChange,
  ])

  const defaultDisplayName =
    modelType === 'image_gen' || listMode === 'image_gen'
      ? defaultPage?.default_for_image_gen?.display_name
      : modelType === 'image'
        ? defaultPage?.default_for_vision?.display_name
        : defaultPage?.default_for_text?.display_name

  const defaultLabel = defaultDisplayName
    ? `默认（${defaultDisplayName}）`
    : hasModels
      ? placeholder
      : chatReadinessLabel(defaultPage?.chat_readiness)

  const handleChange = (v: string): void => {
    onChange(v === '__default__' ? null : v)
  }

  const handleMainOpenChange = useCallback((open: boolean): void => {
    setSelectOpen(open)
  }, [])

  if (isError) {
    return (
      <Select
        value="__default__"
        onValueChange={handleChange}
        onOpenChange={(open) => open && refetch()}
        disabled={disabled}
      >
        <SelectTrigger className={className}>
          <SelectValue placeholder="加载失败，点击重试" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="__default__">加载失败，点击重试</SelectItem>
        </SelectContent>
      </Select>
    )
  }

  const mainSelect = (
    <Select
      value={value ?? '__default__'}
      onValueChange={handleChange}
      onOpenChange={handleMainOpenChange}
      disabled={disabled || showLoading}
    >
      <SelectTrigger className={className}>
        {showLoading ? (
          <span className="flex items-center gap-1.5 text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            加载中...
          </span>
        ) : (
          <SelectValue placeholder={hasModels ? defaultLabel : '暂无可用模型'} />
        )}
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="__default__">{defaultLabel}</SelectItem>

        {systemModels.length > 0 ? (
          <SelectGroup>
            <SelectLabel className="flex items-center gap-1">
              <Cpu className="h-3 w-3" />
              系统模型
            </SelectLabel>
            {systemModelRows.map(({ model: m, unavailable, sharedRoute }) => (
              <SelectItem key={m.id} value={m.id} disabled={unavailable}>
                {m.display_name}
                {sharedRoute ? (
                  <span className="ml-1.5 rounded bg-muted px-1 py-0.5 text-[10px] text-muted-foreground">
                    共享路由
                  </span>
                ) : null}
                {unavailable ? (
                  <span className="ml-1.5 text-xs text-muted-foreground">（不可用）</span>
                ) : null}
                {!unavailable && m.config?.description ? (
                  <span className="ml-1.5 text-xs text-muted-foreground">
                    ({m.config.description})
                  </span>
                ) : null}
              </SelectItem>
            ))}
          </SelectGroup>
        ) : null}

        {userModels.length > 0 ? (
          <SelectGroup>
            <SelectLabel className="flex items-center gap-1">
              <User className="h-3 w-3" />
              我的模型
            </SelectLabel>
            {userModelRows.map(({ model: m, unavailable }) => (
              <SelectItem key={m.id} value={m.id} disabled={unavailable}>
                {m.display_name}
                {unavailable ? (
                  <span className="ml-1.5 text-xs text-muted-foreground">（不可用）</span>
                ) : (
                  <span className="ml-1.5 text-xs text-muted-foreground">({m.model_id})</span>
                )}
              </SelectItem>
            ))}
          </SelectGroup>
        ) : null}

        {isFetchingNextPage ? (
          <div className="flex items-center justify-center gap-1.5 py-2 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" />
            加载更多…
          </div>
        ) : null}
      </SelectContent>
    </Select>
  )

  if (!showProviderFilter) {
    return mainSelect
  }

  return (
    <div className="flex min-w-0 flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
      <Select value={channel} onValueChange={setChannel} disabled={disabled || showLoading}>
        <SelectTrigger
          className="h-7 w-full min-w-[6.5rem] max-w-[9rem] border-0 bg-muted/30 text-[11px] shadow-none sm:h-8 sm:text-xs"
          title={PROVIDER_CHANNEL_FILTER_HINT_LONG}
        >
          <SelectValue placeholder="接入通道" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={CHANNEL_ALL}>全部通道</SelectItem>
          {MODEL_PROVIDERS.map((p) => (
            <SelectItem key={p.id} value={p.id}>
              {p.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <div className="min-w-0 flex-1">{mainSelect}</div>
    </div>
  )
}
