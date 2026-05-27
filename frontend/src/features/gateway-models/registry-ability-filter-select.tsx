import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { MODEL_TYPE_LABELS, type ModelType } from '@/types/user-model'

import { CAPABILITY_LABELS, FILTER_ALL, type GatewayCapability } from './constants'

/** 与 backend ``REGISTRY_ABILITY_FILTER_VALUES`` 一致（顺序仅影响下拉展示） */
const REGISTRY_ABILITY_FILTER_VALUES = [
  'text',
  'image',
  'image_gen',
  'video',
  'chat',
  'embedding',
  'video_generation',
  'moderation',
  'audio_transcription',
  'audio_speech',
  'rerank',
] as const

const MODEL_TYPE_KEYS = new Set<ModelType>(['text', 'image', 'image_gen', 'video'])

function registryAbilityFilterLabel(
  value: (typeof REGISTRY_ABILITY_FILTER_VALUES)[number]
): string {
  if (MODEL_TYPE_KEYS.has(value as ModelType)) {
    return MODEL_TYPE_LABELS[value as ModelType]
  }
  if (value in CAPABILITY_LABELS) {
    return CAPABILITY_LABELS[value as GatewayCapability]
  }
  return value
}

/** 注册表列表 ``?type=`` 筛选项（与后端白名单对齐） */
export const REGISTRY_ABILITY_FILTER_OPTIONS: { value: string; label: string }[] =
  REGISTRY_ABILITY_FILTER_VALUES.map((value) => ({
    value,
    label: registryAbilityFilterLabel(value),
  }))

export function RegistryAbilityFilterSelect({
  id,
  value,
  onValueChange,
  className,
}: {
  id?: string
  value: string
  onValueChange: (v: string) => void
  className?: string
}): React.JSX.Element {
  return (
    <Select
      value={value || FILTER_ALL}
      onValueChange={(v) => {
        onValueChange(v === FILTER_ALL ? '' : v)
      }}
    >
      <SelectTrigger
        id={id}
        className={className ?? 'h-8 w-[120px] shrink-0 text-xs'}
        aria-label="按模型能力筛选"
      >
        <SelectValue placeholder="能力" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={FILTER_ALL}>全部能力</SelectItem>
        {REGISTRY_ABILITY_FILTER_OPTIONS.map((opt) => (
          <SelectItem key={opt.value} value={opt.value}>
            {opt.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
