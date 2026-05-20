/**
 * Listing 创作 AI 生成 - 主页面
 *
 * 布局：左侧固定「输入 + 执行」，右侧「分步执行」与「本次产出」双栏。
 * 能力区块采用手风琴模式，同时只展开一个，减少页面垂直高度。
 */

import { useState, useCallback, useMemo, useEffect } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams, useNavigate } from 'react-router-dom'

import { listingStudioApi } from '@/api/listingStudio'
import { Button } from '@/components/ui/button'
import { DEFAULT_LISTING_STUDIO_INPUTS } from '@/constants/listing-studio'
import { useListingStudioCapabilities } from '@/hooks/use-listing-studio-capabilities'
import type { ListingStudioCapabilitiesConfig } from '@/hooks/use-listing-studio-capabilities'
import { useToast } from '@/hooks/use-toast'
import { Zap, Loader2, History, CheckCircle2, XCircle, Circle, Sparkles } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'
import { useListingStudioStore } from '@/stores/listing-studio'
import type { ListingStudioJob } from '@/types/listing-studio'

import { CapabilityBlock } from './components/capability-block'
import { ImageGenPanel } from './components/image-gen-panel'
import { InputPanel } from './components/input-panel'
import {
  getInputSummary,
  inputsToUserInput,
  type ListingStudioInputs,
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
  job: ListingStudioJob | null
  capabilityConfig: ListingStudioCapabilitiesConfig
}): React.JSX.Element {
  const { executionLayers, capabilityNames } = capabilityConfig

  const stepsByCap = useMemo(
    () => new Map(job?.steps?.map((s) => [s.capability_id, s]) ?? []),
    [job?.steps]
  )

  const layerAllCompleted = (layer: string[]): boolean =>
    layer.every((id) => stepsByCap.get(id)?.status === 'completed')

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
                const step = stepsByCap.get(capId)
                return <StepIcon key={capId} status={step?.status} name={capabilityNames[capId]} />
              })}
            </div>
          ) : (
            layer.map((capId) => {
              const step = stepsByCap.get(capId)
              return <StepIcon key={capId} status={step?.status} name={capabilityNames[capId]} />
            })
          )}
        </div>
      ))}
    </div>
  )
}

export default function ListingStudioPage(): React.JSX.Element {
  const { config: caps, isError: capsLoadError } = useListingStudioCapabilities()
  const { jobId: urlJobId } = useParams<{ jobId?: string }>()
  const navigate = useNavigate()

  const currentJobId = urlJobId ?? null

  const setCurrentJobId = useCallback(
    (id: string) => {
      useListingStudioStore.getState().setLastJobId(id)
      navigate(`/listing-studio/${id}`, { replace: true })
    },
    [navigate]
  )

  // 无 URL jobId 时，自动恢复最近任务
  useEffect(() => {
    if (urlJobId) return
    const lastId = useListingStudioStore.getState().lastJobId
    if (lastId) navigate(`/listing-studio/${lastId}`, { replace: true })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps -- 仅首次挂载

  const [inputs, setInputsState] = useState<ListingStudioInputs>(() => {
    const draft = useListingStudioStore.getState().draftInputs
    return Object.keys(draft).length > 0 ? draft : DEFAULT_LISTING_STUDIO_INPUTS
  })
  const setInputs = useCallback(
    (next: ListingStudioInputs | ((prev: ListingStudioInputs) => ListingStudioInputs)) => {
      setInputsState((prev) => {
        const value = typeof next === 'function' ? next(prev) : next
        useListingStudioStore.getState().setDraftInputs(value)
        return value
      })
    },
    []
  )

  const [promptByCapability, setPromptByCapability] = useState<Record<string, string>>({})
  const [imageGenPromptEdits, setImageGenPromptEdits] = useState<string[] | null>(null)
  const [expandedCapId, setExpandedCapId] = useState<string | null>(null)
  const [localContextByCapability, setLocalContextByCapability] = useState<
    Record<string, Record<string, unknown>>
  >({})
  const queryClient = useQueryClient()
  const { toast } = useToast()

  useEffect(() => {
    if (capsLoadError) {
      toast({
        title: '能力配置加载失败',
        description: '已使用本地默认配置，部分能力可能与后端不一致',
        variant: 'destructive',
      })
    }
  }, [capsLoadError, toast])

  const { data: currentJob } = useQuery({
    queryKey: ['listing-studio', 'job', currentJobId],
    queryFn: () => {
      if (!currentJobId) throw new Error('job id required')
      return listingStudioApi.getJob(currentJobId)
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
    queryKey: ['listing-studio', 'image-gen-tasks', currentJobId],
    queryFn: () =>
      listingStudioApi.listImageGenTasks({ limit: 10, jobId: currentJobId ?? undefined }),
    enabled: !!currentJobId,
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return false
      const hasActive = data.items.some((t) => t.status === 'pending' || t.status === 'running')
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
    setImageGenPromptEdits(null)
  }, [currentJobId])

  const derivedImageGenPrompts = useMemo(() => {
    const step = currentJob?.steps?.find((s) => s.capability_id === 'image_gen_prompts')
    const outputKey = caps.outputKeys.image_gen_prompts
    const raw = step?.output_snapshot?.[outputKey]
    if (!Array.isArray(raw) || raw.length === 0) return null
    return raw.map(String).slice(0, 8)
  }, [currentJob?.steps, caps.outputKeys])

  const imageGenPrompts = imageGenPromptEdits ?? derivedImageGenPrompts ?? []

  const ensureJob = useCallback(async (): Promise<string> => {
    if (currentJobId) return currentJobId
    const job = await listingStudioApi.createJob({ title: 'Listing 创作' })
    void queryClient.invalidateQueries({ queryKey: ['listing-studio', 'jobs'] })
    setCurrentJobId(job.id)
    return job.id
  }, [currentJobId, queryClient, setCurrentJobId])

  const runPipelineMutation = useMutation({
    mutationFn: async () => {
      const res = await listingStudioApi.run({
        inputs: inputsToUserInput(inputs),
        session_id: undefined,
      })
      return res
    },
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: ['listing-studio', 'jobs'] })
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
    <div className="listing-studio-page flex min-h-full flex-col bg-background">
      {/* 顶栏 */}
      <header className="border-b border-border/50 bg-card/40 px-5 py-4 sm:px-8 lg:px-10">
        <div className="mx-auto flex max-w-[1800px] items-center justify-between">
          <h1 className="text-lg font-semibold tracking-tight sm:text-xl">Listing 创作 AI 生成</h1>
          <Link
            to="/listing-studio/history"
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
                  capabilityConfig={caps}
                />
                <ImageGenPanel
                  currentJob={currentJob ?? null}
                  prompts={imageGenPrompts}
                  onPromptsChange={setImageGenPromptEdits}
                  capabilityConfig={caps}
                />
              </div>
            </section>
          </div>
        </div>
      </main>
    </div>
  )
}
