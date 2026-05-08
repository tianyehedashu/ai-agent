/**
 * 能力区块：线性流水线布局（上下文 → 提示词 → 结果）
 *
 * 默认执行流程：提示词中的 {{param}} 占位符自动替换后直接执行，无需中间 LLM 生成步骤。
 * 可选「优化提示词」：调用 LLM 将提示词优化为更详细的版本，用户确认后再执行。
 */

import { useState, useCallback, useEffect, useRef, useMemo } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Play,
  RotateCcw,
  Save,
  Loader2,
  FileText,
  ImageIcon,
  Link2,
  ImagePlus,
  Video,
  ChevronDown,
  CheckCircle2,
  XCircle,
  Circle,
  Sparkles,
  Plus,
} from 'lucide-react'

import { ApiError } from '@/api/client'
import { productInfoApi } from '@/api/productInfo'
import { ModelSelector } from '@/components/model-selector'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { ProductInfoCapabilitiesConfig } from '@/hooks/use-product-info-capabilities'
import { useToast } from '@/hooks/use-toast'
import { cn } from '@/lib/utils'
import type {
  ProductInfoJob,
  ProductInfoPromptTemplate,
  ProductInfoStepStatus,
} from '@/types/product-info'

import { inputsToUserInput, type ProductInfoInputs } from './input-panel-shared'
import { PromptEditor } from './prompt-editor'
import { StepContextPanel } from './step-context-panel'
import { StepOutputView } from './step-output-view'

const CAPABILITY_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  image_analysis: ImageIcon,
  product_link_analysis: Link2,
  competitor_link_analysis: Link2,
  video_script: Video,
  image_gen_prompts: ImagePlus,
}

const STATUS_CONFIG: Record<
  string,
  {
    icon: React.ComponentType<{ className?: string }>
    color: string
    bg: string
    label: string
  }
> = {
  completed: {
    icon: CheckCircle2,
    color: 'text-emerald-500',
    bg: 'bg-emerald-500/10',
    label: '已完成',
  },
  failed: { icon: XCircle, color: 'text-destructive', bg: 'bg-destructive/10', label: '失败' },
  running: { icon: Loader2, color: 'text-blue-500', bg: 'bg-blue-500/10', label: '执行中' },
  prompt_generating: {
    icon: Loader2,
    color: 'text-amber-500',
    bg: 'bg-amber-500/10',
    label: '优化中',
  },
  prompt_ready: { icon: Sparkles, color: 'text-blue-500', bg: 'bg-blue-500/10', label: '已优化' },
  pending: { icon: Circle, color: 'text-muted-foreground', bg: 'bg-muted/50', label: '待执行' },
}

/** 从 API/Error 中提取用户可读的失败原因（优先展示后端返回的 detail） */
function getErrorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message
  if (err instanceof Error) return err.message
  return String(err)
}

interface CapabilityBlockProps {
  capabilityId: string
  stepIndex?: number
  job: ProductInfoJob | null
  inputs: ProductInfoInputs
  promptByCapability: Record<string, string>
  onPromptChange: (capabilityId: string, value: string) => void
  localContext: Record<string, unknown>
  onLocalContextChange: (ctx: Record<string, unknown>) => void
  ensureJob?: () => Promise<string>
  disabled?: boolean
  expanded?: boolean
  onToggle?: () => void
  capabilityConfig: ProductInfoCapabilitiesConfig
}

export function CapabilityBlock({
  capabilityId,
  stepIndex,
  job,
  inputs,
  promptByCapability,
  onPromptChange,
  localContext,
  onLocalContextChange,
  ensureJob,
  disabled,
  expanded = false,
  onToggle,
  capabilityConfig,
}: CapabilityBlockProps): React.JSX.Element {
  const [savingTemplateName, setSavingTemplateName] = useState('')
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null)
  const hasAutoFilledDefault = useRef(false)
  const promptTextareaRef = useRef<HTMLTextAreaElement>(null)
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const name = capabilityConfig.capabilityNames[capabilityId] ?? capabilityId
  const Icon = CAPABILITY_ICONS[capabilityId] ?? FileText
  const metaPrompt = promptByCapability[capabilityId] ?? ''

  const step = job?.steps?.find((s) => s.capability_id === capabilityId)

  const { data: defaultPromptRes } = useQuery({
    queryKey: ['product-info', 'default-prompt', capabilityId],
    queryFn: () => productInfoApi.getDefaultPrompt(capabilityId),
  })
  const defaultPrompt = defaultPromptRes?.content ?? ''

  const { data: templatesData } = useQuery({
    queryKey: ['product-info', 'templates', capabilityId],
    queryFn: () => productInfoApi.listTemplates(capabilityId, { limit: 50 }),
  })
  const templates = templatesData?.items ?? []

  useEffect(() => {
    const hasMeta = typeof step?.meta_prompt === 'string' && step.meta_prompt !== ''
    if (!expanded || !defaultPrompt || metaPrompt !== '' || hasMeta) return
    if (hasAutoFilledDefault.current) return
    hasAutoFilledDefault.current = true
    onPromptChange(capabilityId, defaultPrompt)
  }, [expanded, defaultPrompt, metaPrompt, step?.meta_prompt, capabilityId, onPromptChange])

  useEffect(() => {
    hasAutoFilledDefault.current = false
  }, [capabilityId])

  const buildUserInput = useCallback(() => {
    const base = inputsToUserInput(inputs)
    const result = { ...base }
    const userInputKeys = new Set([
      'product_link',
      'competitor_link',
      'product_name',
      'keywords',
      'image_urls',
    ])
    for (const [k, v] of Object.entries(localContext)) {
      if (userInputKeys.has(k)) continue
      const isEmpty = v === undefined || v === '' || (Array.isArray(v) && v.length === 0)
      if (!isEmpty) result[k] = v
    }
    return result
  }, [inputs, localContext])

  const requiredInputFields = capabilityConfig.capabilityInputFields[capabilityId] ?? []
  const missingRequiredInputs = (() => {
    const userInput = buildUserInput()
    for (const key of requiredInputFields) {
      const value = userInput[key]
      if (key === 'image_urls') {
        if (!Array.isArray(value) || value.length === 0) return true
      } else if (typeof value === 'string') {
        if (!value.trim()) return true
      } else if (value === undefined || value === null || value === '') {
        return true
      }
    }
    return false
  })()

  const updateJobCache = useCallback(
    (data: ProductInfoJob) => {
      queryClient.setQueryData(['product-info', 'job', data.id], data)
      void queryClient.invalidateQueries({ queryKey: ['product-info', 'jobs'] })
    },
    [queryClient]
  )

  const optimizePromptMutation = useMutation({
    mutationFn: async () => {
      const jobId = job?.id ?? (ensureJob ? await ensureJob() : null)
      if (!jobId) throw new Error('请先创建任务')
      return productInfoApi.optimizePrompt(jobId, {
        capability_id: capabilityId,
        user_input: buildUserInput(),
        meta_prompt: metaPrompt === '' ? undefined : metaPrompt,
        model_id: selectedModelId,
      })
    },
    onSuccess: (data) => {
      if (data.optimized_prompt) {
        onPromptChange(capabilityId, data.optimized_prompt)
      }
      toast({ title: '提示词已优化' })
    },
    onError: (err) => {
      toast({ title: '优化失败', description: getErrorMessage(err), variant: 'destructive' })
    },
  })

  const executeMutation = useMutation({
    mutationFn: async () => {
      const jobId = job?.id ?? (ensureJob ? await ensureJob() : null)
      if (!jobId) throw new Error('请先创建任务')
      return productInfoApi.runStep(jobId, {
        capability_id: capabilityId,
        user_input: buildUserInput(),
        model_id: selectedModelId,
        meta_prompt: metaPrompt === '' ? undefined : metaPrompt,
      })
    },
    onSuccess: (data) => {
      updateJobCache(data)
      toast({ title: '执行完成' })
    },
    onError: (err) => {
      toast({ title: '执行失败', description: getErrorMessage(err), variant: 'destructive' })
    },
  })

  const isAnyRunning = optimizePromptMutation.isPending || executeMutation.isPending

  const actualStatus: ProductInfoStepStatus = optimizePromptMutation.isPending
    ? 'prompt_generating'
    : executeMutation.isPending
      ? 'running'
      : (step?.status ?? 'pending')
  const statusCfg = STATUS_CONFIG[actualStatus] ?? STATUS_CONFIG.pending
  const StatusIcon = statusCfg.icon

  const saveTemplateMutation = useMutation({
    mutationFn: async (templateName: string) => {
      const isImageGen = capabilityId === 'image_gen_prompts'
      return productInfoApi.createTemplate(capabilityId, {
        name: templateName,
        content: isImageGen ? undefined : metaPrompt,
        prompts: isImageGen && metaPrompt ? metaPrompt.split('\n').filter(Boolean) : undefined,
      })
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['product-info', 'templates', capabilityId] })
      setSavingTemplateName('')
      toast({ title: '已保存为模板' })
    },
    onError: (err) => {
      toast({ title: '保存失败', description: getErrorMessage(err), variant: 'destructive' })
    },
  })

  const handleRestoreDefault = (): void => {
    onPromptChange(capabilityId, defaultPrompt)
    toast({ title: '已恢复为默认提示词' })
  }

  const handleLoadTemplate = (t: ProductInfoPromptTemplate): void => {
    if (t.content) onPromptChange(capabilityId, t.content)
    else if (t.prompts?.length) onPromptChange(capabilityId, t.prompts.join('\n'))
    toast({ title: `已加载模板：${t.name}` })
  }

  const handleSaveAsTemplate = (): void => {
    const trimmed = savingTemplateName.trim()
    const n = trimmed !== '' ? trimmed : `模板 ${new Date().toLocaleString()}`
    saveTemplateMutation.mutate(n)
  }

  const metaPromptParams = capabilityConfig.metaPromptParams[capabilityId] ?? []

  const resolvedValues = useMemo(() => {
    const base = inputsToUserInput(inputs)
    const capOrder = capabilityConfig.capabilityOrder
    const currentIdx = capOrder.indexOf(capabilityId)
    if (job?.steps && currentIdx >= 0) {
      for (const priorCapId of capOrder.slice(0, currentIdx)) {
        const priorStep = job.steps.find((s) => s.capability_id === priorCapId)
        if (priorStep?.status === 'completed' && priorStep.output_snapshot) {
          Object.assign(base, priorStep.output_snapshot)
        }
      }
    }
    for (const [k, v] of Object.entries(localContext)) {
      if (v !== undefined && v !== '') base[k] = v
    }
    return base
  }, [inputs, localContext, job?.steps, capabilityId, capabilityConfig.capabilityOrder])

  const handleInsertParam = (paramKey: string): void => {
    const placeholder = `{{${paramKey}}}`
    const ta = promptTextareaRef.current
    if (ta) {
      const start = ta.selectionStart
      const end = ta.selectionEnd
      const before = metaPrompt.slice(0, start)
      const after = metaPrompt.slice(end)
      const next = before + placeholder + after
      onPromptChange(capabilityId, next)
      requestAnimationFrame(() => {
        ta.focus()
        const newPos = start + placeholder.length
        ta.setSelectionRange(newPos, newPos)
      })
    } else {
      onPromptChange(capabilityId, metaPrompt + placeholder)
    }
  }

  return (
    <div
      className={cn(
        'rounded-lg border bg-card transition-all duration-200',
        expanded ? 'border-border shadow-sm' : 'border-border/40 hover:border-border/70'
      )}
    >
      {/* Header */}
      <button
        type="button"
        className={cn(
          'flex w-full items-center gap-3 px-4 py-3 text-left transition-colors',
          expanded ? 'rounded-t-lg' : 'rounded-lg',
          !expanded && 'hover:bg-muted/30'
        )}
        onClick={onToggle}
      >
        {typeof stepIndex === 'number' && (
          <span
            className={cn(
              'flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold tabular-nums transition-colors',
              actualStatus === 'completed' && 'bg-emerald-500/15 text-emerald-600',
              (actualStatus === 'running' || actualStatus === 'prompt_generating') &&
                'bg-blue-500/15 text-blue-600',
              actualStatus === 'failed' && 'bg-destructive/15 text-destructive',
              actualStatus === 'prompt_ready' && 'bg-blue-500/15 text-blue-600',
              actualStatus === 'pending' && 'bg-muted text-muted-foreground'
            )}
          >
            {stepIndex}
          </span>
        )}
        <span className="bg-primary/8 flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-primary">
          <Icon className="h-4 w-4" />
        </span>
        <span className="min-w-0 flex-1 truncate text-sm font-semibold">{name}</span>
        <span
          className={cn(
            'flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
            statusCfg.bg,
            statusCfg.color
          )}
        >
          <StatusIcon
            className={cn(
              'h-3.5 w-3.5',
              (actualStatus === 'running' || actualStatus === 'prompt_generating') && 'animate-spin'
            )}
          />
          <span className="hidden sm:inline">{statusCfg.label}</span>
        </span>
        <ChevronDown
          className={cn(
            'h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200',
            expanded && 'rotate-180'
          )}
        />
      </button>

      {/* Linear pipeline content */}
      {expanded && (
        <div className="space-y-5 border-t border-border/50 px-4 pb-4 pt-4">
          {/* Shared model selector (applies to both prompt generation & execution) */}
          <div className="flex items-center justify-between rounded-md bg-muted/40 px-3 py-2">
            <span className="text-xs font-medium text-muted-foreground">模型</span>
            <ModelSelector
              modelType={capabilityConfig.capabilityModelTypes[capabilityId] ?? 'text'}
              value={selectedModelId}
              onChange={setSelectedModelId}
              placeholder={
                capabilityConfig.capabilityModelTypes[capabilityId] === 'image'
                  ? '默认视觉模型'
                  : '默认模型'
              }
              disabled={(disabled ?? false) || isAnyRunning}
              className="h-8 w-[200px] text-sm"
            />
          </div>

          {/* Section 1: Input Context */}
          <StepContextPanel
            capabilityId={capabilityId}
            globalInputs={inputs}
            job={job}
            localContext={localContext}
            onLocalContextChange={onLocalContextChange}
            disabled={(disabled ?? false) || isAnyRunning}
            capabilityConfig={capabilityConfig}
          />

          {/* Section 2: Prompt + Actions */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                提示词
              </p>
              <div className="flex items-center gap-2">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-8 gap-1.5 rounded-md px-3 text-sm"
                      disabled={(disabled ?? false) || isAnyRunning}
                    >
                      <FileText className="h-3.5 w-3.5" />
                      模板
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="min-w-[180px]">
                    <DropdownMenuItem onClick={handleRestoreDefault} disabled={disabled ?? false}>
                      <RotateCcw className="h-4 w-4" />
                      <span className="ml-2">恢复默认</span>
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    {templates.length === 0 ? (
                      <DropdownMenuItem disabled>暂无模板</DropdownMenuItem>
                    ) : (
                      templates.map((t) => (
                        <DropdownMenuItem
                          key={t.id}
                          onClick={() => {
                            handleLoadTemplate(t)
                          }}
                          disabled={disabled ?? false}
                        >
                          {t.name}
                        </DropdownMenuItem>
                      ))
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>

                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 rounded-md px-3 text-sm"
                  onClick={(e) => {
                    e.stopPropagation()
                    optimizePromptMutation.mutate()
                  }}
                  disabled={(disabled ?? false) || isAnyRunning || missingRequiredInputs}
                  title={
                    missingRequiredInputs
                      ? '请先填写本步骤必填参数（如图片、产品名称等）'
                      : '使用 AI 优化当前提示词（可选）'
                  }
                >
                  {optimizePromptMutation.isPending ? (
                    <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                  )}
                  优化提示词
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label className="text-sm font-medium text-foreground">提示词</Label>
                {metaPromptParams.length > 0 && (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="h-7 gap-1 rounded px-2 text-xs"
                        disabled={(disabled ?? false) || isAnyRunning}
                      >
                        <Plus className="h-3 w-3" />
                        插入参数
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="start" className="min-w-[180px]">
                      {metaPromptParams.map((p) => (
                        <DropdownMenuItem
                          key={p.key}
                          onClick={() => {
                            handleInsertParam(p.key)
                          }}
                          disabled={(disabled ?? false) || isAnyRunning}
                        >
                          <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{`{{${p.key}}}`}</code>
                          <span className="ml-2 text-muted-foreground">{p.label}</span>
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}
                <div className="flex items-center gap-1.5">
                  <Input
                    type="text"
                    placeholder="模板名称"
                    className="h-7 w-28 rounded text-xs"
                    value={savingTemplateName}
                    onChange={(e) => {
                      setSavingTemplateName(e.target.value)
                    }}
                    disabled={(disabled ?? false) || isAnyRunning}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 rounded px-2 text-xs"
                    onClick={handleSaveAsTemplate}
                    disabled={(disabled ?? false) || isAnyRunning || saveTemplateMutation.isPending}
                  >
                    <Save className="mr-1 h-3 w-3" />
                    保存
                  </Button>
                </div>
              </div>
              <PromptEditor
                textareaRef={promptTextareaRef}
                placeholder="可使用「插入参数」添加 {{product_name}} 等占位符，执行时自动替换为实际值。可选使用「优化提示词」让 AI 改进。"
                value={metaPrompt}
                onChange={(v) => {
                  onPromptChange(capabilityId, v)
                }}
                params={metaPromptParams}
                resolvedValues={resolvedValues}
                disabled={(disabled ?? false) || isAnyRunning}
                rows={14}
              />
            </div>
          </div>

          {/* Arrow separator */}
          <div className="flex items-center gap-2 px-2">
            <div className="h-px flex-1 bg-border/40" />
            <ChevronDown className="h-4 w-4 text-muted-foreground/40" />
            <div className="h-px flex-1 bg-border/40" />
          </div>

          {/* Section 3: Execute + Result */}
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-2">
              <p className="shrink-0 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                执行结果
              </p>
              <Button
                type="button"
                size="sm"
                className="h-8 rounded-md px-4 text-sm"
                onClick={(e) => {
                  e.stopPropagation()
                  executeMutation.mutate()
                }}
                disabled={
                  (disabled ?? false) ||
                  isAnyRunning ||
                  missingRequiredInputs ||
                  (!job?.id && !ensureJob)
                }
                title={
                  missingRequiredInputs ? '请先填写本步骤必填参数（如图片、产品名称等）' : undefined
                }
              >
                {executeMutation.isPending ? (
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Play className="mr-1.5 h-3.5 w-3.5" />
                )}
                执行
              </Button>
            </div>

            {step &&
            step.status !== 'pending' &&
            step.status !== 'prompt_generating' &&
            step.status !== 'prompt_ready' ? (
              <StepOutputView step={step} defaultExpanded={true} />
            ) : (
              <p className="rounded-md border border-dashed border-border/40 py-8 text-center text-sm text-muted-foreground">
                执行后在此展示结果
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
