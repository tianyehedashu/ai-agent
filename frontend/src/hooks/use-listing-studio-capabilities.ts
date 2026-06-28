/**
 * Listing Studio 能力配置 - API 驱动，失败时回退到本地 fallback 常量
 */

import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import { listingStudioApi } from '@/api/listing-studio'
import {
  CAPABILITY_ORDER,
  CAPABILITY_NAMES,
  OUTPUT_KEYS,
  CAPABILITY_MODEL_TYPES,
  META_PROMPT_PARAMS,
  CAPABILITY_DEPENDENCIES,
  CAPABILITY_INPUT_FIELDS,
} from '@/constants/listing-studio'
import type { ListingStudioCapability } from '@/types/listing-studio'
import type { ModelType } from '@/types/user-model'

export interface ListingStudioCapabilitiesConfig {
  capabilityOrder: readonly string[]
  capabilityNames: Record<string, string>
  outputKeys: Record<string, string>
  capabilityModelTypes: Record<string, ModelType>
  metaPromptParams: Record<string, { key: string; label: string }[]>
  capabilityDependencies: Record<string, string[]>
  capabilityInputFields: Record<string, string[]>
  executionLayers: string[][]
}

export interface ListingStudioCapabilitiesResult {
  config: ListingStudioCapabilitiesConfig
  isLoading: boolean
  isError: boolean
  isFallback: boolean
}

/** 模块级单例，避免 loading/error 时每轮 render 产生新引用 */
const FALLBACK_CAPABILITIES_CONFIG = getFallbackCapabilitiesConfig()

export function getFallbackCapabilitiesConfig(): ListingStudioCapabilitiesConfig {
  const capabilityOrder = CAPABILITY_ORDER
  return {
    capabilityOrder,
    capabilityNames: CAPABILITY_NAMES,
    outputKeys: OUTPUT_KEYS,
    capabilityModelTypes: CAPABILITY_MODEL_TYPES,
    metaPromptParams: META_PROMPT_PARAMS,
    capabilityDependencies: CAPABILITY_DEPENDENCIES,
    capabilityInputFields: CAPABILITY_INPUT_FIELDS,
    executionLayers: [capabilityOrder.slice(0, 3), ['video_script'], ['image_gen_prompts']],
  }
}

export function deriveCapabilitiesFromApi(
  caps: ListingStudioCapability[],
  executionLayers: string[][]
): ListingStudioCapabilitiesConfig {
  const fallback = getFallbackCapabilitiesConfig()
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

  const layers = executionLayers.length > 0 ? executionLayers : fallback.executionLayers

  return {
    capabilityOrder,
    capabilityNames,
    outputKeys,
    capabilityModelTypes,
    metaPromptParams,
    capabilityDependencies,
    capabilityInputFields,
    executionLayers: layers,
  }
}

export function useListingStudioCapabilities(): ListingStudioCapabilitiesResult {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['listing-studio', 'capabilities'],
    queryFn: () => listingStudioApi.listCapabilities(),
    staleTime: 5 * 60 * 1000,
  })

  return useMemo(() => {
    if (isLoading) {
      return {
        config: FALLBACK_CAPABILITIES_CONFIG,
        isLoading: true,
        isError: false,
        isFallback: true,
      }
    }

    if (isError || data === undefined || data.capabilities.length === 0) {
      return {
        config: FALLBACK_CAPABILITIES_CONFIG,
        isLoading: false,
        isError,
        isFallback: true,
      }
    }

    return {
      config: deriveCapabilitiesFromApi(data.capabilities, data.execution_layers),
      isLoading: false,
      isError: false,
      isFallback: false,
    }
  }, [data, isLoading, isError])
}
