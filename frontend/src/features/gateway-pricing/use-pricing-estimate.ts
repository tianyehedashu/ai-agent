import { useQuery } from '@tanstack/react-query'

import { gatewayApi, type PricingEstimateResult } from '@/api/gateway'
import { formatMoney } from '@/lib/money'
import { getCurrentTeamId } from '@/stores/gateway-team'

export function formatPricingEstimateUsd(result: PricingEstimateResult): string {
  const usd = Number.parseFloat(result.downstream_revenue_usd)
  if (!Number.isFinite(usd) || usd < 0) return '—'
  return formatMoney(usd, { currency: 'USD', precision: 6 })
}

export function usePricingEstimate(params: {
  gatewayModelId: string | null | undefined
  inputTokens: number | undefined
  completionTokens: number | undefined
  enabled: boolean
}): {
  label: string | null
  isLoading: boolean
  isApiEstimate: boolean
} {
  const teamId = getCurrentTeamId()
  const pin = params.inputTokens ?? 0
  const pout = params.completionTokens ?? 0
  const hasUsage = pin + pout > 0
  const modelId = params.gatewayModelId?.trim() ?? ''

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['gateway-pricing-estimate', teamId, modelId, pin, pout],
    queryFn: () => {
      if (!teamId) return Promise.reject(new Error('未选择团队'))
      return gatewayApi.estimatePricing(teamId, {
        gateway_model_id: modelId,
        input_tokens: pin,
        output_tokens: pout,
      })
    },
    enabled: params.enabled && Boolean(teamId) && Boolean(modelId) && hasUsage,
    staleTime: 30_000,
  })

  if (!params.enabled || !modelId || !hasUsage) {
    return { label: null, isLoading: false, isApiEstimate: false }
  }
  if (isLoading || isFetching) {
    return { label: null, isLoading: true, isApiEstimate: false }
  }
  if (!data) {
    return { label: null, isLoading: false, isApiEstimate: false }
  }
  return {
    label: `${formatPricingEstimateUsd(data)}（预估）`,
    isLoading: false,
    isApiEstimate: true,
  }
}
