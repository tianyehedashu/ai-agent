/**
 * ModelSelector - 通用模型选择器
 *
 * 显示系统预置模型 + 用户自定义模型，支持按类型过滤。
 * 复用于产品信息步骤、Agent 对话、视频任务等场景。
 */

import { useEffect, useMemo, useState } from 'react'

import { useQuery } from '@tanstack/react-query'
import { Cpu, Loader2, User } from 'lucide-react'

import { userModelApi } from '@/api/userModel'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { PROVIDER_CHANNEL_FILTER_HINT_LONG } from '@/lib/provider-channel-hint'
import type { ModelType } from '@/types/user-model'
import { MODEL_PROVIDERS } from '@/types/user-model'

const CHANNEL_ALL = '__all__'

export type ModelListMode = 'chat' | 'image_gen' | 'video'

interface ModelSelectorProps {
  /** 过滤模型类型 */
  modelType?: ModelType
  /** 与后端 ``/user-models/available?mode=`` 对齐（与 modelType 可同时使用，用于创作模式语义） */
  listMode?: ModelListMode
  /** 当前选中的 model_id (系统模型 ID 或用户模型 UUID) */
  value?: string | null
  /** 选择变更回调 */
  onChange: (modelId: string | null) => void
  /** 占位符文本 */
  placeholder?: string
  /** 是否禁用 */
  disabled?: boolean
  /** 额外 className */
  className?: string
  /** 是否展示「按接入通道」筛选（与设置页列表语义一致） */
  showProviderFilter?: boolean
}

export function ModelSelector({
  modelType,
  listMode,
  value,
  onChange,
  placeholder = '默认模型',
  disabled = false,
  className,
  showProviderFilter = false,
}: ModelSelectorProps): React.JSX.Element {
  const [channel, setChannel] = useState<string>(CHANNEL_ALL)

  const providerForApi = showProviderFilter && channel !== CHANNEL_ALL ? channel : undefined

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: [
      'user-models',
      'available',
      modelType,
      listMode ?? '',
      showProviderFilter ? channel : '',
    ],
    queryFn: () =>
      userModelApi.listAvailable(
        modelType,
        providerForApi,
        listMode ? { mode: listMode } : undefined
      ),
    staleTime: 30_000,
    retry: 1,
  })

  const systemModels = useMemo(() => data?.system_models ?? [], [data])
  const userModels = useMemo(() => data?.user_models ?? [], [data])
  const selectableIds = useMemo(() => {
    const ids = new Set<string>()
    for (const m of systemModels) ids.add(m.id)
    for (const m of userModels) ids.add(m.id)
    return ids
  }, [systemModels, userModels])
  const hasModels = systemModels.length > 0 || userModels.length > 0

  useEffect(() => {
    if (value === null || value === undefined || isLoading || isError) return
    if (!selectableIds.has(value)) {
      onChange(null)
    }
  }, [value, selectableIds, isLoading, isError, onChange])
  const defaultDisplayName =
    modelType === 'image_gen' || listMode === 'image_gen'
      ? data?.default_for_image_gen?.display_name
      : modelType === 'image'
        ? data?.default_for_vision?.display_name
        : data?.default_for_text?.display_name
  const defaultLabel = defaultDisplayName ? `默认（${defaultDisplayName}）` : placeholder

  const handleChange = (v: string): void => {
    onChange(v === '__default__' ? null : v)
  }

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
      disabled={disabled || isLoading}
    >
      <SelectTrigger className={className}>
        {isLoading ? (
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

        {systemModels.length > 0 && (
          <SelectGroup>
            <SelectLabel className="flex items-center gap-1">
              <Cpu className="h-3 w-3" />
              系统模型
            </SelectLabel>
            {systemModels.map((m) => (
              <SelectItem key={m.id} value={m.id}>
                {m.display_name}
                {m.config?.description ? (
                  <span className="ml-1.5 text-xs text-muted-foreground">
                    ({m.config.description})
                  </span>
                ) : null}
              </SelectItem>
            ))}
          </SelectGroup>
        )}

        {userModels.length > 0 && (
          <SelectGroup>
            <SelectLabel className="flex items-center gap-1">
              <User className="h-3 w-3" />
              我的模型
            </SelectLabel>
            {userModels.map((m) => (
              <SelectItem key={m.id} value={m.id}>
                {m.display_name}
                <span className="ml-1.5 text-xs text-muted-foreground">({m.model_id})</span>
              </SelectItem>
            ))}
          </SelectGroup>
        )}
      </SelectContent>
    </Select>
  )

  if (!showProviderFilter) {
    return mainSelect
  }

  return (
    <div className="flex min-w-0 flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
      <Select value={channel} onValueChange={setChannel} disabled={disabled || isLoading}>
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
