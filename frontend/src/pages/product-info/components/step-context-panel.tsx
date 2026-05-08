/**
 * 步骤上下文输入面板：展示和编辑每步的用户输入 + 所有前序步骤的可引用输出
 *
 * - CAPABILITY_DEPENDENCIES 中的依赖步骤：自动注入，标记"推荐"
 * - 其他前序已完成步骤：可手动启用引用
 */

import { useState, useCallback, useMemo, useEffect, useRef } from 'react'

import { ChevronDown, Package, Link2 } from 'lucide-react'

import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { INPUT_FIELDS } from '@/constants/product-info'
import type { ProductInfoCapabilitiesConfig } from '@/hooks/use-product-info-capabilities'
import { cn } from '@/lib/utils'
import type { ProductInfoJob } from '@/types/product-info'

import { FieldRow, ImageUrlListEditor } from './input-panel'
import { FIELD_ICONS, type ProductInfoInputs } from './input-panel-shared'

const USER_INPUT_KEYS = new Set([
  'product_link',
  'competitor_link',
  'product_name',
  'keywords',
  'image_urls',
])

interface PriorStepOutput {
  capId: string
  key: string
  data: unknown
  isDep: boolean
}

interface StepContextPanelProps {
  capabilityId: string
  globalInputs: ProductInfoInputs
  job: ProductInfoJob | null
  localContext: Record<string, unknown>
  onLocalContextChange: (ctx: Record<string, unknown>) => void
  disabled?: boolean
  capabilityConfig: ProductInfoCapabilitiesConfig
}

export function StepContextPanel({
  capabilityId,
  globalInputs,
  job,
  localContext,
  onLocalContextChange,
  disabled,
  capabilityConfig,
}: StepContextPanelProps): React.JSX.Element {
  const [expanded, setExpanded] = useState(false)
  const injectedDepsRef = useRef(new Set<string>())

  const relevantFields = useMemo(
    () => capabilityConfig.capabilityInputFields[capabilityId] ?? [],
    [capabilityConfig.capabilityInputFields, capabilityId]
  )
  const depCapIds = useMemo(
    () => capabilityConfig.capabilityDependencies[capabilityId] ?? [],
    [capabilityConfig.capabilityDependencies, capabilityId]
  )

  const allPriorOutputs = useMemo((): PriorStepOutput[] => {
    const steps = job?.steps
    if (!steps) return []
    const currentIdx = capabilityConfig.capabilityOrder.indexOf(capabilityId)
    if (currentIdx < 0) return []
    return capabilityConfig.capabilityOrder
      .slice(0, currentIdx)
      .map((capId) => {
        const step = steps.find(
          (s) => s.capability_id === capId && s.status === 'completed' && s.output_snapshot
        )
        const snap = step?.output_snapshot
        if (!snap) return null
        const outputKey = capabilityConfig.outputKeys[capId] ?? capId
        const keyed = capabilityConfig.outputKeys[capId]
        const dataOut = keyed ? snap[keyed] : snap
        return { capId, key: outputKey, data: dataOut, isDep: depCapIds.includes(capId) }
      })
      .filter(Boolean) as PriorStepOutput[]
  }, [job?.steps, capabilityId, depCapIds, capabilityConfig])

  const depOutputs = useMemo(() => allPriorOutputs.filter((o) => o.isDep), [allPriorOutputs])
  const optionalOutputs = useMemo(() => allPriorOutputs.filter((o) => !o.isDep), [allPriorOutputs])

  // 首次展开时，将左侧全局输入同步到本地上下文（仅当 localContext 为空时）
  useEffect(() => {
    if (Object.keys(localContext).length > 0) return
    const initial: Record<string, unknown> = {}
    for (const f of relevantFields) {
      const val = (globalInputs as Record<string, unknown>)[f]
      if (f === 'image_urls') {
        if (Array.isArray(val) && val.length > 0) initial[f] = val
      } else if (val !== undefined && val !== '') {
        initial[f] = val
      }
    }
    if (Object.keys(initial).length > 0) onLocalContextChange(initial)
  }, [globalInputs, relevantFields, localContext, onLocalContextChange])

  useEffect(() => {
    const updates: Record<string, unknown> = {}
    for (const f of relevantFields) {
      const globalVal = (globalInputs as Record<string, unknown>)[f]
      const localVal = localContext[f]
      if (f === 'image_urls') {
        if (Array.isArray(globalVal) && globalVal.length > 0) {
          updates[f] = globalVal
        }
      } else if (USER_INPUT_KEYS.has(f)) {
        if (globalVal !== undefined && globalVal !== '') {
          updates[f] = globalVal
        }
      } else if (
        globalVal !== undefined &&
        globalVal !== '' &&
        (localVal === undefined || localVal === '')
      ) {
        updates[f] = globalVal
      }
    }
    if (Object.keys(updates).length > 0) {
      onLocalContextChange({ ...localContext, ...updates })
    }
  }, [globalInputs, relevantFields, localContext, onLocalContextChange])

  useEffect(() => {
    if (depOutputs.length === 0) return
    const updates: Record<string, unknown> = {}
    for (const dep of depOutputs) {
      if (!injectedDepsRef.current.has(dep.capId) && dep.key && dep.data !== undefined) {
        updates[dep.key] = dep.data
        injectedDepsRef.current.add(dep.capId)
      }
    }
    if (Object.keys(updates).length > 0) {
      onLocalContextChange({ ...localContext, ...updates })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 仅在 depOutputs 变化时合并；完整 deps 会导致与 localContext 同步互相触发
  }, [depOutputs])

  const handleFieldChange = useCallback(
    (key: string, value: unknown) => {
      onLocalContextChange({ ...localContext, [key]: value })
    },
    [localContext, onLocalContextChange]
  )

  const handleToggleOptional = useCallback(
    (item: PriorStepOutput, active: boolean) => {
      if (active) {
        onLocalContextChange({ ...localContext, [item.key]: item.data })
      } else {
        const next = Object.fromEntries(
          Object.entries(localContext).filter(([k]) => k !== item.key)
        )
        onLocalContextChange(next)
      }
    },
    [localContext, onLocalContextChange]
  )

  const displayContext = useMemo(
    () =>
      ({ ...(globalInputs as Record<string, unknown>), ...localContext }) as Record<
        string,
        unknown
      >,
    [globalInputs, localContext]
  )

  const summaryParts: string[] = []
  for (const f of relevantFields) {
    const v = displayContext[f]
    if (f === 'image_urls' && Array.isArray(v) && v.length > 0) {
      summaryParts.push(`图片 ${String(v.length)} 张`)
    } else if (v && typeof v !== 'object') {
      const label = INPUT_FIELDS.find((ff) => ff.key === f)?.label ?? f
      summaryParts.push(label)
    }
  }
  const injectedCount = allPriorOutputs.filter((o) => localContext[o.key] !== undefined).length
  if (injectedCount > 0) {
    summaryParts.push(`引用 ${String(injectedCount)} 个前步结果`)
  }
  const summary = summaryParts.length > 0 ? summaryParts.join('、') : '无输入'

  return (
    <div className="rounded-md border border-border/40 bg-muted/20">
      <button
        type="button"
        className="flex w-full items-center gap-2.5 px-4 py-2.5 text-left text-sm transition-colors hover:bg-muted/40"
        onClick={() => {
          setExpanded((e) => !e)
        }}
      >
        <ChevronDown
          className={cn(
            'h-4 w-4 shrink-0 text-muted-foreground transition-transform',
            expanded && 'rotate-180'
          )}
        />
        <span className="font-medium text-muted-foreground">输入上下文</span>
        {!expanded && (
          <span className="min-w-0 flex-1 truncate text-sm text-muted-foreground/70">
            {summary}
          </span>
        )}
      </button>

      {expanded && (
        <div className="space-y-4 border-t border-border/30 px-4 pb-4 pt-3">
          {relevantFields.length > 0 && (
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                用户输入
              </p>
              {relevantFields.map((fKey) => {
                if (fKey === 'image_urls') {
                  const urls = displayContext[fKey] as string[] | undefined
                  const list = Array.isArray(urls) ? urls : []
                  return (
                    <ImageUrlListEditor
                      key={fKey}
                      urls={list}
                      onChange={(urls) => {
                        handleFieldChange(fKey, urls)
                      }}
                      disabled={disabled}
                      compact
                      label="图片链接"
                    />
                  )
                }
                const fieldDef = INPUT_FIELDS.find((ff) => ff.key === fKey)
                if (!fieldDef) return null
                const fromLocal = localContext[fKey]
                const fromGlobal = (globalInputs as Record<string, unknown>)[fKey]
                const val =
                  typeof fromLocal === 'string' && fromLocal !== ''
                    ? fromLocal
                    : typeof fromGlobal === 'string'
                      ? fromGlobal
                      : ''
                return (
                  <FieldRow
                    key={fKey}
                    fieldKey={`ctx-${capabilityId}-${fKey}`}
                    label={fieldDef.label}
                    placeholder={fieldDef.placeholder}
                    value={val}
                    onChange={(v) => {
                      handleFieldChange(fKey, v === '' ? undefined : v)
                    }}
                    disabled={disabled}
                    icon={FIELD_ICONS[fKey] ?? Package}
                  />
                )
              })}
            </div>
          )}

          {depOutputs.length > 0 && (
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                依赖步骤结果（自动引用，可编辑）
              </p>
              {depOutputs.map((dep) => (
                <DepOutputEditor
                  key={dep.capId}
                  capId={dep.capId}
                  outputKey={dep.key}
                  data={localContext[dep.key] ?? dep.data}
                  onChange={(val) => {
                    handleFieldChange(dep.key, val)
                  }}
                  disabled={disabled}
                  capabilityNames={capabilityConfig.capabilityNames}
                />
              ))}
            </div>
          )}

          {optionalOutputs.length > 0 && (
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                可引用的前步结果
              </p>
              {optionalOutputs.map((item) => {
                const isActive = localContext[item.key] !== undefined
                return (
                  <OptionalStepRef
                    key={item.capId}
                    item={item}
                    isActive={isActive}
                    onToggle={(active) => {
                      handleToggleOptional(item, active)
                    }}
                    data={localContext[item.key] ?? item.data}
                    onChange={(val) => {
                      handleFieldChange(item.key, val)
                    }}
                    disabled={disabled}
                    capabilityNames={capabilityConfig.capabilityNames}
                  />
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function DepOutputEditor({
  capId,
  outputKey,
  data,
  onChange,
  disabled,
  capabilityNames,
}: {
  capId: string
  outputKey: string
  data: unknown
  onChange: (val: unknown) => void
  disabled?: boolean
  capabilityNames: Record<string, string>
}): React.JSX.Element {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState(() =>
    typeof data === 'string' ? data : JSON.stringify(data, null, 2)
  )
  const [parseError, setParseError] = useState<string | null>(null)

  const handleBlur = (): void => {
    try {
      const parsed: unknown = JSON.parse(text)
      setParseError(null)
      onChange(parsed)
    } catch {
      setParseError('JSON 格式错误')
    }
  }

  const name = capabilityNames[capId] ?? capId
  const preview = text.length > 80 ? `${text.slice(0, 80)}...` : text

  return (
    <div className="rounded-md border border-border/30 bg-background/50">
      <button
        type="button"
        className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm hover:bg-muted/30"
        onClick={() => {
          setOpen((o) => !o)
        }}
      >
        <ChevronDown
          className={cn(
            'h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform',
            open && 'rotate-180'
          )}
        />
        <span className="font-medium">{outputKey}</span>
        <span className="text-xs text-muted-foreground/60">({name})</span>
        {!open && (
          <span className="min-w-0 flex-1 truncate font-mono text-xs text-muted-foreground/50">
            {preview}
          </span>
        )}
      </button>
      {open && (
        <div className="border-t border-border/20 p-3">
          <Label className="sr-only">{outputKey}</Label>
          <Textarea
            value={text}
            onChange={(e) => {
              setText(e.target.value)
            }}
            onBlur={handleBlur}
            disabled={disabled}
            rows={6}
            className="font-mono text-sm leading-relaxed"
          />
          {parseError && <p className="mt-1 text-xs text-destructive">{parseError}</p>}
        </div>
      )}
    </div>
  )
}

function OptionalStepRef({
  item,
  isActive,
  onToggle,
  data,
  onChange,
  disabled,
  capabilityNames,
}: {
  item: PriorStepOutput
  isActive: boolean
  onToggle: (active: boolean) => void
  data: unknown
  onChange: (val: unknown) => void
  disabled?: boolean
  capabilityNames: Record<string, string>
}): React.JSX.Element {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState(() =>
    typeof data === 'string' ? data : JSON.stringify(data, null, 2)
  )
  const [parseError, setParseError] = useState<string | null>(null)

  useEffect(() => {
    setText(typeof data === 'string' ? data : JSON.stringify(data, null, 2))
  }, [data])

  const handleBlur = (): void => {
    if (!isActive) return
    try {
      const parsed: unknown = JSON.parse(text)
      setParseError(null)
      onChange(parsed)
    } catch {
      setParseError('JSON 格式错误')
    }
  }

  const name = capabilityNames[item.capId] ?? item.capId
  const preview = text.length > 80 ? `${text.slice(0, 80)}...` : text

  return (
    <div
      className={cn(
        'rounded-md border bg-background/50 transition-colors',
        isActive ? 'border-primary/30' : 'border-border/30'
      )}
    >
      <div className="flex items-center gap-2.5 px-3 py-2">
        <Switch
          checked={isActive}
          onCheckedChange={onToggle}
          disabled={disabled}
          className="scale-75"
        />
        <button
          type="button"
          className="flex min-w-0 flex-1 items-center gap-2 text-left text-sm hover:opacity-80"
          onClick={() => {
            setOpen((o) => !o)
          }}
        >
          <Link2 className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <span className={cn('font-medium', !isActive && 'text-muted-foreground')}>
            {item.key}
          </span>
          <span className="text-xs text-muted-foreground/60">({name})</span>
          {!open && (
            <span className="min-w-0 flex-1 truncate font-mono text-xs text-muted-foreground/50">
              {preview}
            </span>
          )}
          <ChevronDown
            className={cn(
              'h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform',
              open && 'rotate-180'
            )}
          />
        </button>
      </div>
      {open && (
        <div className="border-t border-border/20 p-3">
          <Label className="sr-only">{item.key}</Label>
          <Textarea
            value={text}
            onChange={(e) => {
              setText(e.target.value)
            }}
            onBlur={handleBlur}
            disabled={(disabled ?? false) || !isActive}
            rows={6}
            className={cn('font-mono text-sm leading-relaxed', !isActive && 'opacity-50')}
          />
          {parseError && <p className="mt-1 text-xs text-destructive">{parseError}</p>}
        </div>
      )}
    </div>
  )
}
