/**
 * 模型能力编辑：主调用面 capability + 产品特性 model_types + 出站调用形。
 */

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import { MODEL_TYPE_LABELS } from '@/types/user-model'
import type { ModelType } from '@/types/user-model'

import { CapabilityField } from './capability-field'
import { CAPABILITIES, type GatewayCapability } from './constants'

const PRODUCT_TYPES: ModelType[] = ['text', 'image', 'image_gen', 'video']

const MODEL_TYPE_TO_CAPABILITY: Record<ModelType, string> = {
  text: 'chat',
  image: 'chat',
  image_gen: 'image',
  video: 'video_generation',
}

export interface ModelCapabilityEditorValues {
  capability: string
  modelTypes: ModelType[]
  upstreamCallShape: string
  /** 读侧推导但当前 capability 下不可编辑的历史特性（如 chat 行的 image_gen） */
  legacyModelTypes?: ModelType[]
}

export interface ModelCapabilityEditorProps {
  values: ModelCapabilityEditorValues
  onChange: (values: ModelCapabilityEditorValues) => void
  disabled?: boolean
  /** 个人模型单行编辑：仅允许选一个 model_type */
  singleModelType?: boolean
  className?: string
}

function allowedProductTypes(capability: string): ModelType[] {
  const cap = capability.trim().toLowerCase()
  if (cap === 'chat') return ['text', 'image']
  if (cap === 'image') return ['image_gen']
  if (cap === 'video_generation') return ['video']
  return ['text']
}

function defaultModelTypesForCapability(capability: string, current: ModelType[]): ModelType[] {
  const allowed = allowedProductTypes(capability)
  const kept = current.filter((t) => allowed.includes(t))
  if (kept.length > 0) return kept
  return [allowed[0] ?? 'text']
}

export function ModelCapabilityEditor({
  values,
  onChange,
  disabled = false,
  singleModelType = false,
  className,
}: ModelCapabilityEditorProps): React.JSX.Element {
  const allowed = allowedProductTypes(values.capability)

  function setCapability(capability: string): void {
    const nextTypes = defaultModelTypesForCapability(capability, values.modelTypes)
    onChange({
      ...values,
      capability,
      modelTypes: singleModelType ? [nextTypes[0] ?? 'text'] : nextTypes,
    })
  }

  function toggleType(t: ModelType): void {
    if (disabled || !allowed.includes(t)) return
    if (singleModelType) {
      onChange({
        ...values,
        capability: MODEL_TYPE_TO_CAPABILITY[t],
        modelTypes: [t],
      })
      return
    }
    const current = values.modelTypes
    let next: ModelType[]
    if (current.includes(t)) {
      next = current.filter((x) => x !== t)
      if (next.length === 0) next = ['text']
    } else {
      next = [...current, t]
    }
    onChange({ ...values, modelTypes: next })
  }

  return (
    <div className={cn('space-y-4', className)}>
      <CapabilityField
        id="model-capability"
        value={values.capability}
        onValueChange={setCapability}
        showTooltip
        className={disabled ? 'pointer-events-none opacity-60' : undefined}
      />

      <div className="grid gap-1.5">
        <Label>产品特性</Label>
        <p className="text-xs text-muted-foreground">
          与主调用面不同：如「图片理解」表示 chat 多模态；生图/视频请先将主调用面改为对应类型。
        </p>
        <div className="flex flex-wrap gap-4">
          {PRODUCT_TYPES.map((t) => {
            const typeAllowed = allowed.includes(t)
            return (
              <label
                key={t}
                className={cn(
                  'flex items-center gap-1.5 text-sm',
                  typeAllowed && !disabled ? 'cursor-pointer' : 'cursor-not-allowed opacity-50'
                )}
              >
                <Checkbox
                  checked={values.modelTypes.includes(t)}
                  disabled={disabled || !typeAllowed}
                  onCheckedChange={() => {
                    toggleType(t)
                  }}
                />
                {MODEL_TYPE_LABELS[t]}
              </label>
            )
          })}
        </div>
      </div>

      {(values.legacyModelTypes?.length ?? 0) > 0 ? (
        <Alert>
          <AlertDescription className="space-y-2 text-xs">
            <p>
              历史数据含当前主调用面下不可直接编辑的特性；保存「产品特性」变更时会移除它们。生图/视频请先将主调用面改为对应类型。
            </p>
            <div className="flex flex-wrap gap-1">
              {values.legacyModelTypes?.map((t) => (
                <Badge key={t} variant="outline" className="font-normal">
                  {MODEL_TYPE_LABELS[t]}（只读）
                </Badge>
              ))}
            </div>
          </AlertDescription>
        </Alert>
      ) : null}

      {!singleModelType ? (
        <div className="grid gap-1.5">
          <Label htmlFor="upstream-call-shape">出站调用形</Label>
          <Select
            value={values.upstreamCallShape || '__default__'}
            onValueChange={(v) => {
              onChange({
                ...values,
                upstreamCallShape: v === '__default__' ? '' : v,
              })
            }}
            disabled={disabled}
          >
            <SelectTrigger id="upstream-call-shape">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__default__">跟随凭据方案（默认）</SelectItem>
              <SelectItem value="openai_compat">OpenAI-compat</SelectItem>
              <SelectItem value="anthropic_native">Anthropic-native（实验）</SelectItem>
            </SelectContent>
          </Select>
        </div>
      ) : null}
    </div>
  )
}

export function capabilityEditorValuesFromModel(model: {
  capability: string
  model_types?: string[]
  upstream_call_shape?: string | null
}): ModelCapabilityEditorValues {
  const cap = CAPABILITIES.includes(model.capability as GatewayCapability)
    ? model.capability
    : 'chat'
  const rawTypes = (model.model_types ?? ['text']).filter(
    (t): t is ModelType => t === 'text' || t === 'image' || t === 'image_gen' || t === 'video'
  )
  const allowed = allowedProductTypes(cap)
  const editableTypes = rawTypes.filter((t) => allowed.includes(t))
  const legacyTypes = rawTypes.filter((t) => !allowed.includes(t))
  return {
    capability: cap,
    modelTypes: editableTypes.length > 0 ? editableTypes : ['text'],
    upstreamCallShape: model.upstream_call_shape ?? '',
    legacyModelTypes: legacyTypes.length > 0 ? legacyTypes : undefined,
  }
}

/** 个人模型单行编辑：从 API model_types 推导当前行主 type（vision 行常为 text+image）。 */
export function primaryPersonalModelType(model: {
  capability: string
  model_types?: string[]
  selector_capabilities?: Record<string, unknown>
}): ModelType {
  const types = (model.model_types ?? ['text']).filter(
    (t): t is ModelType => t === 'text' || t === 'image' || t === 'image_gen' || t === 'video'
  )
  const nonText = types.filter((t) => t !== 'text')
  if (nonText.length === 1) return nonText[0]
  const sc = model.selector_capabilities
  if (sc?.supports_video_gen === true) return 'video'
  if (sc?.supports_image_gen === true) return 'image_gen'
  if (sc?.supports_vision === true) return 'image'
  if (model.capability === 'image') return 'image_gen'
  if (model.capability === 'video_generation') return 'video'
  return 'text'
}

export function capabilityEditorValuesFromPersonalModel(model: {
  capability: string
  model_types?: string[]
  upstream_call_shape?: string | null
  selector_capabilities?: Record<string, unknown>
}): ModelCapabilityEditorValues {
  const primary = primaryPersonalModelType(model)
  return {
    capability: MODEL_TYPE_TO_CAPABILITY[primary],
    modelTypes: [primary],
    upstreamCallShape: model.upstream_call_shape ?? '',
  }
}

export function modelCapabilityPatchFromEditor(
  values: ModelCapabilityEditorValues,
  baseline: ModelCapabilityEditorValues
): {
  capability?: string
  model_types?: ModelType[]
  upstream_call_shape?: string | null
} {
  const patch: {
    capability?: string
    model_types?: ModelType[]
    upstream_call_shape?: string | null
  } = {}
  if (values.capability !== baseline.capability) {
    patch.capability = values.capability
  }
  const typesChanged =
    values.modelTypes.length !== baseline.modelTypes.length ||
    values.modelTypes.some((t, i) => t !== baseline.modelTypes[i])
  if (typesChanged) {
    patch.model_types = values.modelTypes
  }
  if (values.upstreamCallShape !== baseline.upstreamCallShape) {
    patch.upstream_call_shape = values.upstreamCallShape.trim() || null
  }
  return patch
}
