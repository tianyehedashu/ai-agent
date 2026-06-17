import { useCallback } from 'react'

import { useMutation, useQueryClient } from '@tanstack/react-query'

import type { QuotaRule, QuotaRuleUpsertBody } from '@/api/gateway'
import { gatewayApi } from '@/api/gateway'
import { useActorCredentialSummaries } from '@/features/gateway-credentials/hooks/use-actor-credential-summaries'
import { useToast } from '@/hooks/use-toast'

import { buildBatchRules, type BuildBatchRulesOptions } from './quota-batch-rules'
import { collectQuotaBatchInvalidationTeamIds, executeQuotaBatchUpsert } from './quota-batch-upsert'
import { deleteQuotaRule } from './quota-rule-delete'
import { gatewayBudgetsBaseQueryKey } from './use-gateway-budgets'
import { gatewayQuotaRulesBaseQueryKey } from './use-gateway-quota-rules'

import type { QuotaBatchFormValues } from './quota-batch-form'
import type { QuotaCenterMode } from './use-quota-center'

interface UseQuotaBatchSubmitOptions {
  teamId: string
  mode: QuotaCenterMode
  selfUserId?: string | null
  onSuccess?: () => void
  /** upstream 层批量展开时过滤非法凭据×模型组合 */
  buildBatchRulesOptions?: BuildBatchRulesOptions
}

function invalidateQuotaCaches(
  queryClient: ReturnType<typeof useQueryClient>,
  teamIds: readonly string[]
): void {
  for (const targetTeamId of teamIds) {
    void queryClient.invalidateQueries({ queryKey: gatewayQuotaRulesBaseQueryKey(targetTeamId) })
    void queryClient.invalidateQueries({ queryKey: gatewayBudgetsBaseQueryKey(targetTeamId) })
  }
}

export function useQuotaBatchSubmit({
  teamId,
  mode,
  selfUserId = null,
  onSuccess,
  buildBatchRulesOptions,
}: UseQuotaBatchSubmitOptions): {
  submitForm: (values: QuotaBatchFormValues) => void
  deleteRule: (budgetId: string) => void
  deleteRuleEntity: (rule: QuotaRule) => void
  batchPending: boolean
  deletePending: boolean
} {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const actorCredentials = useActorCredentialSummaries()

  const batchMutation = useMutation({
    mutationFn: (rules: QuotaRuleUpsertBody[]) =>
      executeQuotaBatchUpsert(teamId, rules, actorCredentials.contextTeamIdByCredentialId, mode),
    onSuccess: (result, rules) => {
      const targetTeamIds = collectQuotaBatchInvalidationTeamIds(
        teamId,
        rules,
        actorCredentials.contextTeamIdByCredentialId
      )
      invalidateQuotaCaches(queryClient, targetTeamIds)
      if (result.failed.length > 0) {
        toast({
          title: `部分成功：${String(result.succeeded.length)} 条`,
          description: result.failed.map((f) => f.error).join('；'),
          variant: 'destructive',
        })
      } else {
        toast({ title: `已保存 ${String(result.succeeded.length)} 条配额规则` })
      }
      onSuccess?.()
    },
    onError: (err: Error) => {
      toast({ title: '保存失败', description: err.message, variant: 'destructive' })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (target: string | QuotaRule) =>
      typeof target === 'string'
        ? mode === 'member'
          ? gatewayApi.deleteSelfQuotaRule(teamId, target)
          : gatewayApi.deleteBudget(teamId, target)
        : deleteQuotaRule(teamId, target, mode),
    onSuccess: () => {
      invalidateQuotaCaches(queryClient, [teamId])
      toast({ title: '已删除配额规则' })
      onSuccess?.()
    },
    onError: (err: Error) => {
      toast({ title: '删除失败', description: err.message, variant: 'destructive' })
    },
  })

  const submitForm = useCallback(
    (formValues: QuotaBatchFormValues): void => {
      let values = formValues
      if (mode === 'member') {
        if (selfUserId === null) {
          toast({ title: '无法识别当前用户', variant: 'destructive' })
          return
        }
        if (
          (values.layer === 'platform' || values.layer === 'upstream') &&
          values.credentialIds.length === 0
        ) {
          toast({
            title: '请选择凭据',
            description:
              values.layer === 'upstream'
                ? '厂商额度须选择本人的 BYOK 凭据。'
                : '自助配额须选择至少一个凭据。',
            variant: 'destructive',
          })
          return
        }
        values = {
          ...values,
          layer: values.layer === 'upstream' ? 'upstream' : 'platform',
          subjectMode: 'users',
          userIds: [selfUserId],
          keyIds: [],
        }
      }
      if (
        values.layer === 'upstream' &&
        values.credentialIds.length > 1 &&
        buildBatchRulesOptions?.realModelsByCredential === undefined
      ) {
        toast({
          title: '无法批量设置',
          description: '多凭据上游配额请从配额中心设置。',
          variant: 'destructive',
        })
        return
      }
      const rules = buildBatchRules(values, buildBatchRulesOptions)
      if (!rules || rules.length === 0) {
        toast({
          title: '请完善表单',
          description: '至少选择主体并填写一项限额',
          variant: 'destructive',
        })
        return
      }
      if (rules.length > 200) {
        toast({ title: '单次最多 200 条', variant: 'destructive' })
        return
      }
      batchMutation.mutate(rules)
    },
    [batchMutation, mode, selfUserId, toast, buildBatchRulesOptions]
  )

  const deleteRule = useCallback(
    (budgetId: string): void => {
      deleteMutation.mutate(budgetId)
    },
    [deleteMutation]
  )

  const deleteRuleEntity = useCallback(
    (rule: QuotaRule): void => {
      deleteMutation.mutate(rule)
    },
    [deleteMutation]
  )

  return {
    submitForm,
    deleteRule,
    deleteRuleEntity,
    batchPending: batchMutation.isPending,
    deletePending: deleteMutation.isPending,
  }
}
