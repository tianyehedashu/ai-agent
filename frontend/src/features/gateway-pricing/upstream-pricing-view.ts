import type { GatewayModel } from '@/api/gateway/models'
import type { UpstreamPricingRow } from '@/api/gateway/pricing'

/** 上游成本固定以 USD 展示（LiteLLM 价表原始币种） */
export const UPSTREAM_DISPLAY_CURRENCY = 'USD' as const

export function upstreamPricingKey(
  provider: string,
  upstreamModel: string,
  capability: string
): string {
  return `${provider}\0${upstreamModel}\0${capability || 'chat'}`
}

export function buildLinkedModelKeys(models: readonly GatewayModel[]): Set<string> {
  const keys = new Set<string>()
  for (const model of models) {
    if (!model.enabled || !model.real_model.trim()) continue
    keys.add(upstreamPricingKey(model.provider, model.real_model, model.capability))
  }
  return keys
}

export interface ModelMissingUpstream {
  gatewayName: string
  provider: string
  upstreamModel: string
  capability: string
}

/** 一次构建上游价目键集合，供过滤与缺价诊断复用（js-set-map-lookups） */
export function buildUpstreamPricingKeySet(
  upstreamRows: readonly UpstreamPricingRow[]
): Set<string> {
  const keys = new Set<string>()
  for (const row of upstreamRows) {
    keys.add(upstreamPricingKey(row.provider, row.upstream_model, row.capability))
  }
  return keys
}

export function findModelsMissingUpstream(
  models: readonly GatewayModel[],
  upstreamKeys: ReadonlySet<string>
): ModelMissingUpstream[] {
  const missing: ModelMissingUpstream[] = []
  for (const model of models) {
    if (!model.enabled || !model.real_model.trim()) continue
    const capability = model.capability || 'chat'
    const key = upstreamPricingKey(model.provider, model.real_model, capability)
    if (upstreamKeys.has(key)) continue
    missing.push({
      gatewayName: model.name,
      provider: model.provider,
      upstreamModel: model.real_model,
      capability,
    })
  }
  return missing.sort((a, b) => a.gatewayName.localeCompare(b.gatewayName))
}

export function filterUpstreamRows(
  rows: readonly UpstreamPricingRow[],
  options: {
    effectiveProviders: ReadonlySet<string>
    linkedKeys: ReadonlySet<string>
    onlyLinkedModels: boolean
    /** 空集表示不按提供商子集过滤 */
    selectedProviders: ReadonlySet<string>
  }
): UpstreamPricingRow[] {
  const filterByProvider = options.selectedProviders.size > 0
  const result: UpstreamPricingRow[] = []
  for (const row of rows) {
    if (!options.effectiveProviders.has(row.provider)) continue
    if (filterByProvider && !options.selectedProviders.has(row.provider)) continue
    if (options.onlyLinkedModels) {
      const key = upstreamPricingKey(row.provider, row.upstream_model, row.capability)
      if (!options.linkedKeys.has(key)) continue
    }
    result.push(row)
  }
  return result
}
