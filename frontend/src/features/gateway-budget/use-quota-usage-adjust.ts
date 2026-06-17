import { useMutation, useQueryClient } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import type { QuotaRule, QuotaUsageAdjustmentBody } from '@/api/gateway/quota-rules'
import { useToast } from '@/hooks/use-toast'

import { gatewayQuotaRulesBaseQueryKey } from './use-gateway-quota-rules'

import type { QuotaCenterMode } from './use-quota-center'

export function buildQuotaUsageAdjustmentBody(rule: QuotaRule): QuotaUsageAdjustmentBody {
  const ref = rule.source_ref
  return {
    layer: rule.key.layer,
    budget_id: ref.budget_id,
    plan_id: ref.plan_id,
    quota_id: ref.quota_id,
    mode: 'set',
    current_usd:
      rule.usage?.current_usd !== null && rule.usage?.current_usd !== undefined
        ? Number.parseFloat(String(rule.usage.current_usd))
        : 0,
    current_tokens: rule.usage?.current_tokens ?? 0,
    current_requests: rule.usage?.current_requests ?? 0,
  }
}

export function isQuotaRuleUsageAdjustable(rule: QuotaRule): boolean {
  if (rule.source_ref.budget_id) return true
  return rule.source_ref.plan_id !== null && rule.source_ref.quota_id !== null
}

export function useQuotaUsageAdjust(options: {
  teamId: string
  mode: QuotaCenterMode
  onSuccess?: () => void
}): {
  adjustUsage: (body: QuotaUsageAdjustmentBody) => void
  resetWindow: (rule: QuotaRule) => void
  pending: boolean
} {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const mutation = useMutation({
    mutationFn: (body: QuotaUsageAdjustmentBody) =>
      options.mode === 'member'
        ? gatewayApi.adjustSelfQuotaRuleUsage(options.teamId, body)
        : gatewayApi.adjustQuotaRuleUsage(options.teamId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: gatewayQuotaRulesBaseQueryKey(options.teamId),
      })
      toast({ title: '已更新本周期用量' })
      options.onSuccess?.()
    },
    onError: (err: Error) => {
      toast({ title: '用量更新失败', description: err.message, variant: 'destructive' })
    },
  })

  const resetWindow = (rule: QuotaRule): void => {
    const ref = rule.source_ref
    mutation.mutate({
      layer: rule.key.layer,
      budget_id: ref.budget_id,
      plan_id: ref.plan_id,
      quota_id: ref.quota_id,
      mode: 'reset_window',
    })
  }

  return {
    adjustUsage: mutation.mutate,
    resetWindow,
    pending: mutation.isPending,
  }
}
