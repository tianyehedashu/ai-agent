/**
 * 产品信息 AI 生成 - 主页面
 *
 * 布局：左侧固定「输入 + 执行」，右侧「分步执行」与「本次产出」双栏。
 * 能力区块采用手风琴模式，同时只展开一个，减少页面垂直高度。
 */

import { useState, useCallback, useMemo, useEffect } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Zap, Loader2, History, CheckCircle2, XCircle, Circle, Sparkles } from 'lucide-react'
import { Link, useParams, useNavigate } from 'react-router-dom'

import { productInfoApi } from '@/api/productInfo'
import { Button } from '@/components/ui/button'
import { DEFAULT_PRODUCT_INFO_INPUTS } from '@/constants/product-info'
import { useProductInfoCapabilities } from '@/hooks/use-product-info-capabilities'
import type { ProductInfoCapabilitiesConfig } from '@/hooks/use-product-info-capabilities'
import { useToast } from '@/hooks/use-toast'
import { cn } from '@/lib/utils'
import { useProductInfoStore } from '@/stores/product-info'
import type { ProductInfoJob } from '@/types/product-info'

import { CapabilityBlock } from './components/capability-block'
import { ImageGenPanel } from './components/image-gen-panel'
import { InputPanel } from './components/input-panel'
import {
  getInputSummary,
  inputsToUserInput,
  type ProductInfoInputs,
} from './components/input-panel-shared'
import { OutputPreview } from './components/output-preview'
import { pickLatestEightImages } from './components/output-preview-shared'

function StepIcon({ status, name }: { status?: string; name: string }): React.JSX.Element {
  return (
    <div className="group relative flex items-center" title={name}>
      {status === 'completed' ? (
        <CheckCircle2 className="h-4 w-4 text-emerald-500" />
      ) : status === 'failed' ? (
        <XCircle className="h-4 w-4 text-destructive" />
      ) : status === 'running' ? (
        <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
      ) : status === 'prompt_generating' ? (
        <Loader2 className="h-4 w-4 animate-spin text-amber-500" />
      ) : status === 'prompt_ready' ? (
        <Sparkles className="h-4 w-4 text-blue-500" />
      ) : (
        <Circle className="h-4 w-4 text-muted-foreground/40" />
      )}
    </div>
  )
}

function StepProgressBar({
  job,
  capabilityConfig,
}: {
  job: ProductInfoJob | null
  capabilityConfig: ProductInfoCapabilitiesConfig
}): React.JSX.Element {
  const { executionLayers, capabilityNames } = capabilityConfig

  const layerAllCompleted = (layer: string[]): boolean =>
    layer.every((id) => job?.steps?.find((s) => s.capability_id === id)?.status === 'completed')

  return (
    <div className="flex items-center gap-1.5">
      {executionLayers.map((layer, layerIdx) => (
        <div key={layerIdx} className="flex items-center gap-1.5">
          {layerIdx > 0 && (
            <div
              className={cn(
                'h-px w-3 transition-colors sm:w-5',
                layerAllCompleted(executionLayers[layerIdx - 1]) ? 'bg-emerald-400' : 'bg-border'
              )}
            />
          )}
          {layer.length > 1 ? (
            <div className="flex items-center gap-0.5 rounded-full bg-muted/50 px-1 py-0.5">
              {layer.map((capId) => {
                const step = job?.steps?.find((s) => s.capability_id === capId)
                return <StepIcon key={capId} status={step?.status} name={capabilityNames[capId]} />
              })}
            </div>
          ) : (
            layer.map((capId) => {
              const step = job?.steps?.find((s) => s.capability_id === capId)
              return <StepIcon key={capId} status={step?.status} name={capabilityNames[capId]} />
            })
          )}
        </div>
      ))}
    </div>
  )
}

export default function ProductInfoPage(): React.JSX.Element {
  const caps = useProductInfoCapabilities()
  const { jobId: urlJobId } = useParams<{ jobId?: string }>()
  const navigate = useNavigate()

  const currentJobId = urlJobId ?? null

  const setCurrentJobId = useCallback(
    (id: string) => {
      useProductInfoStore.getState().setLastJobId(id)
      navigate(`/product-info/${id}`, { replace: true })
    },
    [navigate]
  )

  // 无 URL jobId 时，自动恢复最近任务
  useEffect(() => {
    if (urlJobId) return
    const lastId = useProductInfoStore.getState().lastJobId
    if (lastId) navigate(`/product-info/${lastId}`, { replace: true })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps -- 仅首次挂载

  const [inputs, setInputsState] = useState<ProductInfoInputs>(() => {
    const draft = useProductInfoStore.getState().draftInputs
    return Object.keys(draft).length > 0 ? draft : DEFAULT_PRODUCT_INFO_INPUTS
  })
  const setInputs = useCallback(
    (next: ProductInfoInputs | ((prev: ProductInfoInputs) => ProductInfoInputs)) => {
      setInputsState((prev) => {
        const value = typeof next === 'function' ? next(prev) : next
        useProductInfoStore.getState().setDraftInputs(value)
        return value
      })
    },
    []
  )

  const [promptByCapability, setPromptByCapability] = useState<Record<string, string>>({})
  const [imageGenPrompts, setImageGenPrompts] = useState<string[]>([])
  const [expandedCapId, setExpandedCapId] = useState<string | null>(null)
  const [localContextByCapability, setLocalContextByCapability] = useState<
    Record<string, Record<string, unknown>>
  >({})
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const { data: currentJob } = useQuery({
    queryKey: ['product-info', 'job', currentJobId],
    queryFn: () => {
      if (!currentJobId) throw new Error('job id required')
      return productInfoApi.getJob(currentJobId)
    },
    enabled: !!currentJobId,
    refetchInterval: (query) => {
      const job = query.state.data
      if (!job) return 3000
      if (job.status === 'running') return 3000
      const hasActiveStep = job.steps?.some(
        (s) => s.status === 'running' || s.status === 'prompt_generating'
      )
      if (hasActiveStep) return 3000
      return false
    },
  })

  const { data: imageGenData } = useQuery({
    queryKey: ['product-info', 'image-gen-tasks'],
    queryFn: () => productInfoApi.listImageGenTasks({ limit: 10 }),
    refetchInterval: (query) => {
      const data = query.state.data as { items?: { status: string }[] } | undefined
      const hasActive = data?.items?.some((t) => t.status === 'pending' || t.status === 'running')
      return hasActive ? 3000 : false
    },
  })
  const latestEightImages = useMemo(
    () => pickLatestEightImages(imageGenData?.items ?? [], currentJob?.id ?? null),
    [imageGenData?.items, currentJob?.id]
  )

  const onPromptChange = useCallback((capabilityId: string, value: string) => {
    setPromptByCapability((prev) => ({ ...prev, [capabilityId]: value }))
  }, [])

  const onLocalContextChange = useCallback((capabilityId: string, ctx: Record<string, unknown>) => {
    setLocalContextByCapability((prev) => ({ ...prev, [capabilityId]: ctx }))
  }, [])

  // 从当前任务的步骤同步 meta_prompt 到本地，保证前后端一致
  useEffect(() => {
    const steps = currentJob?.steps
    if (!steps?.length) return
    setPromptByCapability((prev) => {
      const next = { ...prev }
      for (const step of steps) {
        if (typeof step.meta_prompt === 'string' && step.meta_prompt !== '') {
          next[step.capability_id] = step.meta_prompt
        }
      }
      return next
    })
  }, [currentJob?.id, currentJob?.steps])

  useEffect(() => {
    const step = currentJob?.steps?.find((s) => s.capability_id === 'image_gen_prompts')
    const outputKey = caps.outputKeys.image_gen_prompts
    const raw = step?.output_snapshot?.[outputKey]
    if (!Array.isArray(raw) || raw.length === 0) return
    setImageGenPrompts((prev) => (prev.length > 0 ? prev : raw.map(String).slice(0, 8)))
  }, [currentJob?.id, currentJob?.steps, caps.outputKeys])

  const ensureJob = useCallback(async (): Promise<string> => {
    if (currentJobId) return currentJobId
    const job = await productInfoApi.createJob({ title: '产品信息' })
    void queryClient.invalidateQueries({ queryKey: ['product-info', 'jobs'] })
    setCurrentJobId(job.id)
    return job.id
  }, [currentJobId, queryClient, setCurrentJobId])

  const runPipelineMutation = useMutation({
    mutationFn: async () => {
      const res = await productInfoApi.run({
        inputs: inputsToUserInput(inputs),
        session_id: undefined,
      })
      return res
    },
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: ['product-info', 'jobs'] })
      setCurrentJobId(res.job_id)
      toast({ title: '已开始执行', description: '右侧结果将陆续更新' })
    },
    onError: (err) => {
      toast({ title: '执行失败', description: String(err), variant: 'destructive' })
    },
  })

  const inputSummary = getInputSummary(inputs)
  const completedCount = currentJob?.steps?.filter((s) => s.status === 'completed').length ?? 0

  return (
    <div className="product-info-page flex min-h-full flex-col bg-background">
      {/* 顶栏 */}
      <header className="border-b border-border/50 bg-card/40 px-5 py-4 sm:px-8 lg:px-10">
        <div className="mx-auto flex max-w-[1800px] items-center justify-between">
          <h1 className="text-lg font-semibold tracking-tight sm:text-xl">产品信息 AI 生成</h1>
          <Link
            to="/product-info/history"
            className="flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <History className="h-4 w-4" />
            历史记录
          </Link>
        </div>
      </header>

      {/* 主内容 */}
      <main className="flex-1 px-5 py-6 sm:px-8 lg:px-10">
        <div className="mx-auto grid max-w-[1800px] grid-cols-1 gap-6 lg:grid-cols-[minmax(0,380px)_1fr] lg:gap-10">
          {/* 左侧：输入 + 一键执行 */}
          <aside className="lg:sticky lg:top-4 lg:self-start">
            <div className="rounded-lg border border-border/60 bg-card shadow-sm">
              <div className="border-b border-border/40 px-5 py-3">
                <h2 className="text-base font-semibold text-foreground">输入与执行</h2>
                {inputSummary && (
                  <p className="mt-1 text-sm text-muted-foreground">{inputSummary}</p>
                )}
              </div>
              <div className="p-5">
                <InputPanel inputs={inputs} onChange={setInputs} compact />
                <Button
                  size="lg"
                  className="mt-5 w-full rounded-lg font-medium"
                  onClick={() => {
                    runPipelineMutation.mutate()
                  }}
                  disabled={runPipelineMutation.isPending}
                >
                  {runPipelineMutation.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Zap className="mr-2 h-4 w-4" />
                  )}
                  一键执行全部步骤
                </Button>
              </div>
            </div>
          </aside>

          {/* 右侧 */}
          <div className="min-w-0 space-y-8">
            {/* 分步执行 */}
            <section>
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <h2 className="text-base font-semibold text-foreground">分步执行</h2>
                  {completedCount > 0 && (
                    <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-600">
                      {completedCount}/{caps.capabilityOrder.length} 完成
                    </span>
                  )}
                </div>
                <StepProgressBar job={currentJob ?? null} capabilityConfig={caps} />
              </div>
              <div className="space-y-3">
                {caps.capabilityOrder.map((capId, index) => (
                  <CapabilityBlock
                    key={capId}
                    capabilityId={capId}
                    stepIndex={index + 1}
                    job={currentJob ?? null}
                    inputs={inputs}
                    promptByCapability={promptByCapability}
                    onPromptChange={onPromptChange}
                    localContext={localContextByCapability[capId] ?? {}}
                    onLocalContextChange={(ctx) => {
                      onLocalContextChange(capId, ctx)
                    }}
                    ensureJob={ensureJob}
                    expanded={expandedCapId === capId}
                    onToggle={() => {
                      setExpandedCapId(expandedCapId === capId ? null : capId)
                    }}
                    capabilityConfig={caps}
                  />
                ))}
              </div>
            </section>

            {/* 本次产出 */}
            <section>
              <h2 className="mb-4 text-base font-semibold text-foreground">本次产出</h2>
              <div className="space-y-6">
                <OutputPreview
                  currentJob={currentJob ?? null}
                  latestEightImages={latestEightImages}
                />
                <ImageGenPanel
                  currentJob={currentJob ?? null}
                  prompts={imageGenPrompts}
                  onPromptsChange={setImageGenPrompts}
                />
              </div>
            </section>
          </div>
        </div>
      </main>
    </div>
  )
}
