/**
 * Listing Studio 8 图生成：模型设置、批量生成、单槽重生成
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import { listingStudioApi } from '@/api/listingStudio'
import { GATEWAY_MODELS_AVAILABLE_QUERY_KEY } from '@/features/gateway-models/query-keys'
import {
  defaultImageGenSizeForProvider,
  imageGenSizesForProvider,
} from '@/features/gateway-shared/image-gen-size-presets'
import { useToast } from '@/hooks/use-toast'
import { MAX_PAGE_SIZE } from '@/lib/pagination'
import type { ProductImageGenTask } from '@/types/listing-studio'

import { mergedImagesToSlotArray, pickLatestEightImages } from '../components/output-preview-shared'
import {
  resolveProductSourceImageUrl,
  resolveSlotReferenceImage,
  type SlotReferenceMode,
} from '../lib/slot-reference-image'

const EMPTY_TASKS: ProductImageGenTask[] = []

async function resolveAvailableModelProvider(modelId: string): Promise<string> {
  let page = 1
  for (;;) {
    const res = await gatewayApi.listAvailableModels('image_gen', undefined, {
      mode: 'image_gen',
      page,
      page_size: MAX_PAGE_SIZE,
    })
    for (const item of res.system_models.items) {
      if (item.id === modelId) return item.provider
    }
    for (const item of res.user_models.items) {
      if (item.id === modelId) return item.provider
    }
    if (!res.system_models.has_next && !res.user_models.has_next) break
    page += 1
  }
  return 'volcengine'
}

export interface UseListingStudioImageGenParams {
  jobId: string | null
  prompts: string[]
  inputImageUrls: string[]
}

export interface UseListingStudioImageGenResult {
  modelId: string | null
  setModelId: (id: string | null) => void
  size: string
  setSize: (size: string) => void
  effectiveSize: string
  sizeOptions: string[]
  selectedProvider: string
  referenceImageUrls: string[]
  setReferenceImageUrls: (urls: string[]) => void
  strength: number
  setStrength: (value: number) => void
  sourceImageUrl: string | null
  latestEightImages: { slot: number; url: string }[] | null
  slotUrls: (string | null)[]
  tasks: ProductImageGenTask[]
  isCreating: boolean
  regeneratingSlot: number | null
  createAll: () => void
  regenerateSlot: (slot: number, mode?: SlotReferenceMode) => void
  generateSingleSlot: (slot: number) => void
}

function paddedPrompts(prompts: string[]): string[] {
  const next = [...prompts]
  while (next.length < 8) next.push('')
  return next.slice(0, 8)
}

export type { SlotReferenceMode }

export function useListingStudioImageGen({
  jobId,
  prompts,
  inputImageUrls,
}: UseListingStudioImageGenParams): UseListingStudioImageGenResult {
  const [modelId, setModelId] = useState<string | null>(null)
  const [size, setSize] = useState('')
  const [referenceImageUrls, setReferenceImageUrls] = useState<string[]>([])
  const [strength, setStrength] = useState(0.7)
  const [regeneratingSlot, setRegeneratingSlot] = useState<number | null>(null)

  const queryClient = useQueryClient()
  const { toast } = useToast()

  const { data: selectedProvider = 'volcengine' } = useQuery({
    queryKey: [...GATEWAY_MODELS_AVAILABLE_QUERY_KEY, 'image_gen', 'provider', modelId],
    queryFn: () => {
      if (modelId === null) {
        throw new Error('modelId is required')
      }
      return resolveAvailableModelProvider(modelId)
    },
    enabled: modelId !== null,
    staleTime: 60_000,
  })

  const sizeOptions = useMemo(
    () => [...imageGenSizesForProvider(selectedProvider)],
    [selectedProvider]
  )
  const effectiveSize = size && sizeOptions.includes(size) ? size : sizeOptions[0]

  useEffect(() => {
    if (size && sizeOptions.includes(size)) return
    setSize(defaultImageGenSizeForProvider(selectedProvider))
  }, [selectedProvider, size, sizeOptions])

  const manualReferenceUrl = referenceImageUrls[0]

  const sourceImageUrl = useMemo(
    () => resolveProductSourceImageUrl(manualReferenceUrl, inputImageUrls),
    [manualReferenceUrl, inputImageUrls]
  )

  const { data: tasksData } = useQuery({
    queryKey: ['listing-studio', 'image-gen-tasks', jobId],
    queryFn: () => listingStudioApi.listImageGenTasks({ limit: 10, jobId: jobId ?? undefined }),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const data = query.state.data as { items?: { status: string }[] } | undefined
      const hasActive = data?.items?.some((t) => t.status === 'pending' || t.status === 'running')
      return hasActive ? 3000 : false
    },
  })
  const tasks = tasksData?.items ?? EMPTY_TASKS

  const latestEightImages = useMemo(() => pickLatestEightImages(tasks, jobId), [tasks, jobId])

  const slotUrls = useMemo(() => mergedImagesToSlotArray(latestEightImages), [latestEightImages])
  const slotUrlsRef = useRef(slotUrls)
  slotUrlsRef.current = slotUrls

  const buildPromptItem = useCallback(
    (slot: number, prompt: string, referenceUrl: string | null) => {
      const item: Record<string, unknown> = {
        slot,
        prompt,
      }
      if (referenceUrl) {
        item.reference_image_url = referenceUrl
        item.strength = strength
      }
      return item
    },
    [strength]
  )

  const submitMutation = useMutation({
    mutationFn: async (body: Parameters<typeof listingStudioApi.createImageGenTask>[0]) =>
      listingStudioApi.createImageGenTask(body),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: ['listing-studio', 'image-gen-tasks', variables.job_id ?? jobId],
      })
      const count = variables.prompts?.length ?? 0
      toast({
        title: count <= 1 ? '已提交单张生成' : '已提交生成，主图将显示在下方',
      })
      setRegeneratingSlot(null)
    },
    onError: (err) => {
      toast({ title: '创建失败', description: String(err), variant: 'destructive' })
      setRegeneratingSlot(null)
    },
  })

  const createAll = useCallback(() => {
    if (!jobId) {
      toast({ title: '请先创建或选择任务', variant: 'destructive' })
      return
    }
    const filled = paddedPrompts(prompts)
    const promptItems = filled.map((p, index) => {
      const slot = index + 1
      const ref =
        slot === 1
          ? resolveSlotReferenceImage({
              mode: 'chain',
              slot,
              sourceImageUrl,
            })
          : undefined
      const item: Record<string, unknown> = { slot, prompt: p }
      if (ref) {
        item.reference_image_url = ref
        item.strength = strength
      }
      return item
    })

    submitMutation.mutate({
      prompts: promptItems,
      job_id: jobId,
      model_id: modelId,
      size: effectiveSize,
    })
  }, [prompts, jobId, modelId, effectiveSize, sourceImageUrl, strength, submitMutation, toast])

  const regenerateSlot = useCallback(
    (slot: number, mode: SlotReferenceMode = 'current') => {
      if (!jobId) {
        toast({ title: '请先创建或选择任务', variant: 'destructive' })
        return
      }
      const prompt = paddedPrompts(prompts)[slot - 1]?.trim()
      if (!prompt) {
        toast({ title: '请先填写该槽提示词', variant: 'destructive' })
        return
      }

      const refUrl = resolveSlotReferenceImage({
        mode,
        slot,
        currentSlotUrl: slotUrlsRef.current[slot - 1],
        sourceImageUrl,
      })

      setRegeneratingSlot(slot)
      submitMutation.mutate({
        prompts: [buildPromptItem(slot, prompt, refUrl)],
        job_id: jobId,
        model_id: modelId,
        size: effectiveSize,
      })
    },
    [prompts, sourceImageUrl, jobId, modelId, effectiveSize, buildPromptItem, submitMutation, toast]
  )

  const generateSingleSlot = useCallback(
    (slot: number) => {
      if (!jobId) {
        toast({ title: '请先创建或选择任务', variant: 'destructive' })
        return
      }
      const prompt = paddedPrompts(prompts)[slot - 1]?.trim()
      if (!prompt) {
        toast({ title: '请先填写该槽提示词', variant: 'destructive' })
        return
      }

      const refUrl = resolveSlotReferenceImage({
        mode: 'chain',
        slot,
        sourceImageUrl,
        slot1GeneratedUrl: slotUrlsRef.current[0],
      })

      setRegeneratingSlot(slot)
      submitMutation.mutate({
        prompts: [buildPromptItem(slot, prompt, refUrl)],
        job_id: jobId,
        model_id: modelId,
        size: effectiveSize,
      })
    },
    [prompts, sourceImageUrl, jobId, modelId, effectiveSize, buildPromptItem, submitMutation, toast]
  )

  return {
    modelId,
    setModelId,
    size,
    setSize,
    effectiveSize,
    sizeOptions,
    selectedProvider,
    referenceImageUrls,
    setReferenceImageUrls,
    strength,
    setStrength,
    sourceImageUrl,
    latestEightImages,
    slotUrls,
    tasks,
    isCreating: submitMutation.isPending,
    regeneratingSlot,
    createAll,
    regenerateSlot,
    generateSingleSlot,
  }
}
