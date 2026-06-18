import { useMutation, useQueryClient } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import type { QuotaRule, QuotaRuleEnablementBody } from '@/api/gateway/quota-rules'
import { useToast } from '@/hooks/use-toast'

import { gatewayQuotaRulesBaseQueryKey } from './use-gateway-quota-rules'
import {
  buildQuotaRuleSourceMutationBody,
  isQuotaRuleUsageAdjustable,
} from './use-quota-usage-adjust'

import type { QuotaCenterMode } from './use-quota-center'

/** 该规则是否可在配额中心就地启用停用（与用量校正同口径：单坐标可定位）。 */
export const isQuotaRuleEnablementEditable = isQuotaRuleUsageAdjustable

function enablementBody(rule: QuotaRule, enabled: boolean): QuotaRuleEnablementBody {
  return {
    ...buildQuotaRuleSourceMutationBody(rule),
    enabled,
  }
}

export function useQuotaRuleEnablement(options: { teamId: string; mode: QuotaCenterMode }): {
  setEnabled: (rule: QuotaRule, enabled: boolean) => void
  pendingRuleId: string | null
} {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const mutation = useMutation({
    mutationFn: ({ rule, enabled }: { rule: QuotaRule; enabled: boolean }) =>
      options.mode === 'member'
        ? gatewayApi.setSelfQuotaRuleEnablement(options.teamId, enablementBody(rule, enabled))
        : gatewayApi.setQuotaRuleEnablement(options.teamId, enablementBody(rule, enabled)),
    onSuccess: (_data, { enabled }) => {
      void queryClient.invalidateQueries({
        queryKey: gatewayQuotaRulesBaseQueryKey(options.teamId),
      })
      toast({ title: enabled ? '已启用配额规则' : '已停用配额规则' })
    },
    onError: (err: Error) => {
      toast({ title: '操作失败', description: err.message, variant: 'destructive' })
    },
  })

  const pendingRef = mutation.isPending ? mutation.variables.rule.source_ref : undefined

  return {
    setEnabled: (rule, enabled) => {
      mutation.mutate({ rule, enabled })
    },
    pendingRuleId: pendingRef ? (pendingRef.quota_id ?? pendingRef.budget_id ?? null) : null,
  }
}
