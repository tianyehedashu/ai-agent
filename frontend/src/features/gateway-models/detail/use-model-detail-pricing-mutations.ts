import { useMutation, useQueryClient } from '@tanstack/react-query'

import { gatewayApi, type DownstreamPricingUpsertBody } from '@/api/gateway'
import { pricingApi, type UpstreamPricingUpsertBody } from '@/api/gateway/pricing'
import { GATEWAY_DISPLAY_CURRENCY } from '@/features/gateway-pricing/display-currency'
import { UPSTREAM_DISPLAY_CURRENCY } from '@/features/gateway-pricing/upstream-pricing-view'
import { useToast } from '@/hooks/use-toast'

interface UseModelDetailPricingMutationsOptions {
  teamId: string
  onDownstreamSuccess?: () => void
  onUpstreamSuccess?: () => void
}

export function useModelDetailPricingMutations({
  teamId,
  onDownstreamSuccess,
  onUpstreamSuccess,
}: UseModelDetailPricingMutationsOptions): {
  upsertDownstream: (body: DownstreamPricingUpsertBody) => void
  restoreDownstreamMirror: (gatewayModelId: string) => void
  upsertUpstream: (body: UpstreamPricingUpsertBody) => void
  downstreamPending: boolean
  upstreamPending: boolean
} {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const currency = GATEWAY_DISPLAY_CURRENCY

  const invalidatePricing = (): void => {
    void queryClient.invalidateQueries({ queryKey: ['gateway-pricing-downstream'] })
    void queryClient.invalidateQueries({ queryKey: ['gateway-pricing-my'] })
    void queryClient.invalidateQueries({ queryKey: ['gateway-pricing-upstream'] })
  }

  const downstreamMutation = useMutation({
    mutationFn: (body: DownstreamPricingUpsertBody) =>
      gatewayApi.createDownstreamPricing(teamId, body),
    onSuccess: (_data, body) => {
      invalidatePricing()
      toast({
        title: body.inheritance_strategy === 'mirror' ? '已恢复跟随上游' : '下游售价已保存为新版本',
      })
      onDownstreamSuccess?.()
    },
    onError: (e: Error) => {
      toast({ title: '保存失败', description: e.message, variant: 'destructive' })
    },
  })

  const upstreamMutation = useMutation({
    mutationFn: (body: UpstreamPricingUpsertBody) => pricingApi.createUpstreamPricing(teamId, body),
    onSuccess: () => {
      invalidatePricing()
      toast({ title: '上游成本已保存为新版本' })
      onUpstreamSuccess?.()
    },
    onError: (e: Error) => {
      toast({ title: '保存失败', description: e.message, variant: 'destructive' })
    },
  })

  const restoreDownstreamMirror = (gatewayModelId: string): void => {
    downstreamMutation.mutate({
      scope: 'tenant',
      gateway_model_id: gatewayModelId,
      inheritance_strategy: 'mirror',
      currency,
      amount_per_million: null,
    })
  }

  return {
    upsertDownstream: (body) => {
      downstreamMutation.mutate(body)
    },
    restoreDownstreamMirror,
    upsertUpstream: (body) => {
      upstreamMutation.mutate(body)
    },
    downstreamPending: downstreamMutation.isPending,
    upstreamPending: upstreamMutation.isPending,
  }
}

export { UPSTREAM_DISPLAY_CURRENCY }
