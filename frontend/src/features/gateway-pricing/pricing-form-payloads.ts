import type { DownstreamPricingUpsertBody, UpstreamPricingUpsertBody } from '@/api/gateway'
import type { DisplayCurrency } from '@/types/money'

export interface UpstreamPricingFormValues {
  provider: string
  upstream_model: string
  capability: string
  input: string
  output: string
  cache_creation: string
  cache_read: string
}

export interface DownstreamPricingFormValues {
  gateway_model_id: string
  inheritance_strategy: 'mirror' | 'manual'
  input: string
  output: string
  cache_creation: string
  cache_read: string
  per_request: string
}

function toOptionalNumber(value: string): number | null {
  const trimmed = value.trim()
  if (!trimmed) return null
  const n = Number(trimmed)
  return Number.isFinite(n) ? n : null
}

export function buildUpstreamPricingPayload(
  values: UpstreamPricingFormValues,
  currency: DisplayCurrency
): UpstreamPricingUpsertBody {
  return {
    provider: values.provider,
    upstream_model: values.upstream_model.trim(),
    capability: values.capability.trim() || 'chat',
    currency,
    amount_per_million: {
      input: Number(values.input),
      output: Number(values.output),
      cache_creation: toOptionalNumber(values.cache_creation),
      cache_read: toOptionalNumber(values.cache_read),
    },
  }
}

export function buildDownstreamPricingPayload(
  values: DownstreamPricingFormValues,
  currency: DisplayCurrency
): DownstreamPricingUpsertBody {
  const gatewayModelId = values.gateway_model_id.trim() || null
  if (values.inheritance_strategy === 'mirror') {
    return {
      scope: 'tenant',
      gateway_model_id: gatewayModelId,
      inheritance_strategy: 'mirror',
      currency,
      amount_per_million: null,
    }
  }
  return {
    scope: 'tenant',
    gateway_model_id: gatewayModelId,
    inheritance_strategy: 'manual',
    currency,
    amount_per_million: {
      input: Number(values.input),
      output: Number(values.output),
      cache_creation: toOptionalNumber(values.cache_creation),
      cache_read: toOptionalNumber(values.cache_read),
      per_request: toOptionalNumber(values.per_request),
    },
  }
}
