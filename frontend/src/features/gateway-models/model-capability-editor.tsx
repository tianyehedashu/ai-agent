/**
 * 模型能力编辑：主调用面 capability + 产品特性 model_types + 出站调用形。
 */

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
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
import { contextWindowEditorValue } from './context-window-display'
import {
  needsVolcengineImageEndpointSetup,
  VOLCENGINE_IMAGE_ENDPOINT_HINT,
} from './volcengine-image-readiness'

const PRODUCT_TYPES: ModelType[] = ['text', 'image', 'image_gen', 'video']

export interface UpstreamCallShapeSelectProps {
  value: string
  onValueChange: (value: string) => void
  disabled?: boolean
  id?: string
  className?: string
}

export function UpstreamCallShapeSelect({
  value,
  onValueChange,
  disabled = false,
  id = 'upstream-call-shape',
  className,
}: UpstreamCallShapeSelectProps): React.JSX.Element {
  return (
    <div className={cn('grid gap-1.5', className)}>
      <Label htmlFor={id}>出站调用形</Label>
      <Select
        value={value || '__default__'}
        onValueChange={(v) => {
          onValueChange(v === '__default__' ? '' : v)
        }}
        disabled={disabled}
      >
        <SelectTrigger id={id}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="__default__">跟随凭据方案（默认）</SelectItem>
          <SelectItem value="openai_compat">OpenAI-compat</SelectItem>
          <SelectItem value="anthropic_native">Anthropic-native（实验）</SelectItem>
        </SelectContent>
      </Select>
    </div>
  )
}

const THINKING_PARAM_OPTIONS: { value: string; label: string }[] = [
  { value: '__auto__', label: '自动（跟随推断）' },
  { value: 'none', label: '无（显式禁用）' },
  { value: 'dashscope_enable_thinking', label: 'Qwen3 思考' },
  { value: 'builtin_reasoning', label: '内置推理' },
  { value: 'anthropic_extended', label: 'Extended Thinking' },
  { value: 'deepseek_v4_thinking', label: 'V4 思考' },
]

const VALID_THINKING_PARAMS: readonly string[] = [
  'dashscope_enable_thinking',
  'builtin_reasoning',
  'anthropic_extended',
  'deepseek_v4_thinking',
]

export interface ThinkingParamSelectProps {
  value: string
  onValueChange: (value: string) => void
  disabled?: boolean
  id?: string
  className?: string
}

export function ThinkingParamSelect({
  value,
  onValueChange,
  disabled = false,
  id = 'thinking-param',
  className,
}: ThinkingParamSelectProps): React.JSX.Element {
  return (
    <div className={cn('grid gap-1.5', className)}>
      <Label htmlFor={id}>思考模式</Label>
      <Select
        value={value || '__auto__'}
        onValueChange={(v) => {
          onValueChange(v === '__auto__' ? '' : v)
        }}
        disabled={disabled}
      >
        <SelectTrigger id={id}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {THINKING_PARAM_OPTIONS.map((opt) => (
            <SelectItem key={opt.value} value={opt.value}>
              {opt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <p className="text-xs text-muted-foreground">
        选择“自动”时由后端按模型名推断；手动指定后优先使用所选值。
      </p>
    </div>
  )
}

export interface ModelCapabilityEditorValues {
  capability: string
  modelTypes: ModelType[]
  upstreamCallShape: string
  /** 思考模式：'' 表示自动（跟随后端推断），否则为 ThinkingParam 值 */
  thinkingParam: string
  /** 上下文窗口（tokens）：'' 表示未设置，由 Router 跳过上下文窗口预检 */
  contextWindow: string
  /** 读侧推导但当前 capability 下不可编辑的历史特性（如 chat 行的 image_gen） */
  legacyModelTypes?: ModelType[]
}

export interface ModelCapabilityEditorProps {
  values: ModelCapabilityEditorValues
  onChange: (values: ModelCapabilityEditorValues) => void
  disabled?: boolean
  /** 隐藏出站调用形选择（个人模型 API 不支持此字段） */
  hideUpstreamCallShape?: boolean
  /** 隐藏思考模式选择（个人模型不支持出站调用形等字段时可选） */
  hideThinkingParam?: boolean
  /** 绑定凭据 provider，用于火山生图前置校验提示 */
  credentialProvider?: string
  /** 绑定凭据 extra，用于检测 image_endpoint_id */
  credentialExtra?: Record<string, unknown> | null
  /** 绑定凭据展示名（提示文案用） */
  credentialName?: string
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
  hideUpstreamCallShape = false,
  hideThinkingParam = false,
  credentialProvider,
  credentialExtra,
  credentialName,
  className,
}: ModelCapabilityEditorProps): React.JSX.Element {
  const allowed = allowedProductTypes(values.capability)
  const showVolcengineImageSetup =
    credentialProvider !== undefined &&
    needsVolcengineImageEndpointSetup(credentialProvider, values.capability, credentialExtra)

  function setCapability(capability: string): void {
    const nextTypes = defaultModelTypesForCapability(capability, values.modelTypes)
    onChange({
      ...values,
      capability,
      modelTypes: nextTypes,
    })
  }

  function toggleType(t: ModelType): void {
    if (disabled || !allowed.includes(t)) return
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

      {showVolcengineImageSetup ? (
        <Alert variant="destructive">
          <AlertTitle>火山生图凭据未就绪</AlertTitle>
          <AlertDescription className="space-y-2 text-xs">
            <p>{VOLCENGINE_IMAGE_ENDPOINT_HINT}</p>
            {credentialName ? (
              <p>
                当前绑定凭据：<span className="font-medium">{credentialName}</span>
              </p>
            ) : null}
            <p>请先在「Gateway → 凭据」中编辑该凭据，填写「生图接入点 ID」后再保存并测试连通性。</p>
          </AlertDescription>
        </Alert>
      ) : null}

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

      {!hideUpstreamCallShape ? (
        <UpstreamCallShapeSelect
          value={values.upstreamCallShape}
          onValueChange={(v) => {
            onChange({ ...values, upstreamCallShape: v })
          }}
          disabled={disabled}
        />
      ) : null}

      {!hideThinkingParam ? (
        <ThinkingParamSelect
          value={values.thinkingParam}
          onValueChange={(v) => {
            onChange({ ...values, thinkingParam: v })
          }}
          disabled={disabled}
        />
      ) : null}

      <div className="grid gap-1.5">
        <Label htmlFor="model-context-window">上下文窗口（tokens）</Label>
        <Input
          id="model-context-window"
          inputMode="numeric"
          className="tabular-nums"
          placeholder="如 262144（留空=不做上下文预检）"
          value={values.contextWindow}
          disabled={disabled}
          onChange={(e) => {
            onChange({ ...values, contextWindow: e.target.value })
          }}
        />
        <p className="text-xs text-muted-foreground">
          上游模型的最大输入 token；填写后 Router 会按此做请求超长预检与展示，留空则跳过。
        </p>
      </div>
    </div>
  )
}

/** 从 tags 解析 thinking_param 回显值；'' 表示 auto（跟随推断）。 */
function resolveThinkingParamFromTags(tags?: Record<string, unknown> | null): string {
  if (!tags) return ''
  if (tags.thinking_param_locked === true && tags.thinking_param === 'none') {
    return 'none'
  }
  const tp = tags.thinking_param
  if (typeof tp === 'string' && tp !== 'none' && VALID_THINKING_PARAMS.includes(tp)) {
    return tp
  }
  return ''
}

export function capabilityEditorValuesFromModel(model: {
  capability: string
  model_types?: string[]
  upstream_call_shape?: string | null
  tags?: Record<string, unknown> | null
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
    thinkingParam: resolveThinkingParamFromTags(model.tags),
    contextWindow: contextWindowEditorValue(undefined, model.tags),
    legacyModelTypes: legacyTypes.length > 0 ? legacyTypes : undefined,
  }
}

export function capabilityEditorValuesFromPersonalModel(model: {
  capability: string
  model_types?: string[]
  upstream_call_shape?: string | null
  selector_capabilities?: Record<string, unknown>
  tags?: Record<string, unknown> | null
}): ModelCapabilityEditorValues {
  const base = capabilityEditorValuesFromModel(model)
  // 个人模型可能无 tags 暴露，从 selector_capabilities 回显
  const contextWindow =
    base.contextWindow || contextWindowEditorValue(model.selector_capabilities, model.tags)
  let thinkingParam = base.thinkingParam
  if (!thinkingParam) {
    const scThinking = model.selector_capabilities?.thinking_param
    if (
      typeof scThinking === 'string' &&
      scThinking !== 'none' &&
      VALID_THINKING_PARAMS.includes(scThinking)
    ) {
      thinkingParam = scThinking
    }
  }
  return { ...base, thinkingParam, contextWindow }
}

export function modelCapabilityPatchFromEditor(
  values: ModelCapabilityEditorValues,
  baseline: ModelCapabilityEditorValues
): {
  capability?: string
  model_types?: ModelType[]
  upstream_call_shape?: string | null
  tags?: Record<string, unknown> | null
} {
  const patch: {
    capability?: string
    model_types?: ModelType[]
    upstream_call_shape?: string | null
    tags?: Record<string, unknown> | null
  } = {}
  const tagsPatch: Record<string, unknown> = {}
  if (values.capability !== baseline.capability) {
    patch.capability = values.capability
    if (values.capability === 'image' && baseline.capability !== 'image') {
      tagsPatch.supports_image_gen = true
      tagsPatch.supports_txt2img = true
    }
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
  // tags 为增量合并（后端 merged_tags.update）：累加各 tag 变更后一次性赋值，避免相互覆盖。
  if (values.thinkingParam !== baseline.thinkingParam) {
    if (values.thinkingParam === '') {
      // auto：清除显式设置
      tagsPatch.thinking_param = null
      tagsPatch.thinking_param_locked = null
    } else if (values.thinkingParam === 'none') {
      // 显式禁用：锁定阻止推断覆盖
      tagsPatch.thinking_param = 'none'
      tagsPatch.thinking_param_locked = true
    } else {
      tagsPatch.thinking_param = values.thinkingParam
      tagsPatch.thinking_param_locked = null
    }
  }
  if (values.contextWindow !== baseline.contextWindow) {
    const trimmed = values.contextWindow.trim()
    if (trimmed === '') {
      tagsPatch.context_window = null
    } else {
      const parsed = Number.parseInt(trimmed, 10)
      // 仅在有效正整数时落库；非法输入视为无变更，避免写入垃圾值。
      if (Number.isInteger(parsed) && parsed > 0) {
        tagsPatch.context_window = parsed
      }
    }
  }
  if (Object.keys(tagsPatch).length > 0) {
    patch.tags = tagsPatch
  }
  return patch
}
