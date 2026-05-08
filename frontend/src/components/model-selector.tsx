/**
 * ModelSelector - 通用模型选择器
 *
 * 显示系统预置模型 + 用户自定义模型，支持按类型过滤。
 * 复用于产品信息步骤、Agent 对话、视频任务等场景。
 */

import { useMemo } from 'react'

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
import type { ModelType } from '@/types/user-model'

interface ModelSelectorProps {
  /** 过滤模型类型 */
  modelType?: ModelType
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
}

export function ModelSelector({
  modelType,
  value,
  onChange,
  placeholder = '默认模型',
  disabled = false,
  className,
}: ModelSelectorProps): React.JSX.Element {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['user-models', 'available', modelType],
    queryFn: () => userModelApi.listAvailable(modelType),
    staleTime: 30_000,
    retry: 1,
  })

  const systemModels = useMemo(() => data?.system_models ?? [], [data])
  const userModels = useMemo(() => data?.user_models ?? [], [data])
  const hasModels = systemModels.length > 0 || userModels.length > 0
  const defaultDisplayName =
    modelType === 'image_gen'
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
          <SelectItem value="__default__">
            <span className="text-muted-foreground">加载失败，点击重试</span>
          </SelectItem>
        </SelectContent>
      </Select>
    )
  }

  return (
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
        <SelectItem value="__default__">
          <span className="text-muted-foreground">{defaultLabel}</span>
        </SelectItem>

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
}
