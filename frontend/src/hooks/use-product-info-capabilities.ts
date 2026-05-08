/**
 * 产品信息能力配置 - API 驱动，失败时回退到本地常量
 */

import { useQuery } from '@tanstack/react-query'

import { productInfoApi } from '@/api/productInfo'
import {
  CAPABILITY_ORDER,
  CAPABILITY_NAMES,
  OUTPUT_KEYS,
  CAPABILITY_MODEL_TYPES,
  META_PROMPT_PARAMS,
  CAPABILITY_DEPENDENCIES,
  CAPABILITY_INPUT_FIELDS,
} from '@/constants/product-info'
import type { ModelType } from '@/types/user-model'

export interface ProductInfoCapabilitiesConfig {
  capabilityOrder: readonly string[]
  capabilityNames: Record<string, string>
  outputKeys: Record<string, string>
  capabilityModelTypes: Record<string, ModelType>
  metaPromptParams: Record<string, { key: string; label: string }[]>
  capabilityDependencies: Record<string, string[]>
  capabilityInputFields: Record<string, string[]>
  executionLayers: string[][]
}

/** 按依赖关系将能力分组为并行执行层（与后端 _build_execution_layers 一致） */
export function buildExecutionLayers(
  order: readonly string[],
  dependencies: Record<string, string[]>
): string[][] {
  const capSet = new Set(order)
  const completed = new Set<string>()
  let remaining = [...order]
  const layers: string[][] = []

  while (remaining.length > 0) {
    const layer: string[] = []
    const still: string[] = []
    for (const id of remaining) {
      const deps = (dependencies[id] ?? []).filter((d) => capSet.has(d))
      if (deps.every((d) => completed.has(d))) {
        layer.push(id)
      } else {
        still.push(id)
      }
    }
    if (layer.length === 0) {
      layers.push(...still.map((id) => [id]))
      break
    }
    layers.push(layer)
    for (const id of layer) completed.add(id)
    remaining = still
  }

  return layers
}

function getFallbackConfig(): ProductInfoCapabilitiesConfig {
  return {
    capabilityOrder: CAPABILITY_ORDER,
    capabilityNames: CAPABILITY_NAMES,
    outputKeys: OUTPUT_KEYS,
    capabilityModelTypes: CAPABILITY_MODEL_TYPES,
    metaPromptParams: META_PROMPT_PARAMS,
    capabilityDependencies: CAPABILITY_DEPENDENCIES,
    capabilityInputFields: CAPABILITY_INPUT_FIELDS,
    executionLayers: buildExecutionLayers(CAPABILITY_ORDER, CAPABILITY_DEPENDENCIES),
  }
}

function deriveFromApi(
  caps: Array<{
    id: string
    name: string
    sort_order?: number
    model_type?: 'text' | 'image'
    output_key?: string
    dependencies?: string[]
    input_fields?: string[]
    meta_prompt_params?: { key: string; label: string }[]
  }>
): ProductInfoCapabilitiesConfig {
  const fallback = getFallbackConfig()
  const sorted = [...caps].sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
  const capabilityOrder = sorted.map((c) => c.id)
  const capabilityNames: Record<string, string> = {}
  const outputKeys: Record<string, string> = {}
  const capabilityModelTypes: Record<string, ModelType> = {}
  const metaPromptParams: Record<string, { key: string; label: string }[]> = {}
  const capabilityDependencies: Record<string, string[]> = {}
  const capabilityInputFields: Record<string, string[]> = {}

  for (const c of caps) {
    capabilityNames[c.id] = c.name
    const fallbackOutputKey = c.id in fallback.outputKeys ? fallback.outputKeys[c.id] : undefined
    outputKeys[c.id] = c.output_key ?? fallbackOutputKey ?? c.id
    const fallbackModelType =
      c.id in fallback.capabilityModelTypes ? fallback.capabilityModelTypes[c.id] : undefined
    capabilityModelTypes[c.id] = c.model_type ?? fallbackModelType ?? 'text'
    metaPromptParams[c.id] = c.meta_prompt_params?.length
      ? c.meta_prompt_params
      : (fallback.metaPromptParams[c.id] ?? [])
    capabilityDependencies[c.id] = c.dependencies?.length
      ? c.dependencies
      : (fallback.capabilityDependencies[c.id] ?? [])
    capabilityInputFields[c.id] = c.input_fields?.length
      ? c.input_fields
      : (fallback.capabilityInputFields[c.id] ?? [])
  }

  return {
    capabilityOrder,
    capabilityNames,
    outputKeys,
    capabilityModelTypes,
    metaPromptParams,
    capabilityDependencies,
    capabilityInputFields,
    executionLayers: buildExecutionLayers(capabilityOrder, capabilityDependencies),
  }
}

export function useProductInfoCapabilities(): ProductInfoCapabilitiesConfig {
  const { data: caps, isSuccess } = useQuery({
    queryKey: ['product-info', 'capabilities'],
    queryFn: () => productInfoApi.listCapabilities(),
    staleTime: 5 * 60 * 1000,
  })

  if (!isSuccess) {
    return getFallbackConfig()
  }
  if (caps.length === 0) {
    return getFallbackConfig()
  }
  return deriveFromApi(caps)
}
