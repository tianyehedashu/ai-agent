import { useCallback, useMemo, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import {
  gatewayApi,
  type QuotaRule,
  type QuotaRuleBatchUpsertResponse,
  type QuotaRuleLayer,
  type QuotaRuleUpsertBody,
} from '@/api/gateway'
import { useInfiniteGatewayModelPages } from '@/features/gateway-models/hooks/use-infinite-gateway-model-pages'
import { GATEWAY_MODELS_STALE_MS } from '@/features/gateway-models/utils'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { formatTeamMemberDisplay } from '@/types/permissions'

import { parseOptionalInt, parseOptionalUsd } from './budget-form-utils'
import { buildBudgetModelOptions } from './budget-model-options'
import { quotaRuleRowId, type QuotaRuleLabelContext } from './quota-rule-utils'
import {
  GATEWAY_QUOTA_META_STALE_MS,
  gatewayQuotaRulesQueryKey,
  useGatewayQuotaRules,
} from './use-gateway-quota-rules'

export interface QuotaBatchFormValues {
  layer: QuotaRuleLayer
  subjectMode: 'tenant' | 'users' | 'keys'
  userIds: string[]
  keyIds: string[]
  credentialIds: string[]
  modelNames: string[]
  allModels: boolean
  allCredentials: boolean
  period: 'daily' | 'monthly' | 'total'
  windowSeconds: string
  quotaLabel: string
  limit_usd: string
  soft_limit_usd: string
  limit_tokens: string
  limit_requests: string
}

export const DEFAULT_BATCH_FORM: QuotaBatchFormValues = {
  layer: 'platform',
  subjectMode: 'tenant',
  userIds: [],
  keyIds: [],
  credentialIds: [],
  modelNames: [],
  allModels: true,
  allCredentials: true,
  period: 'monthly',
  windowSeconds: '0',
  quotaLabel: 'default',
  limit_usd: '',
  soft_limit_usd: '',
  limit_tokens: '',
  limit_requests: '',
}

function expandBatchFormValues(
  values: QuotaBatchFormValues,
  credentialIds: readonly string[]
): QuotaBatchFormValues {
  if (values.layer === 'upstream' && values.allCredentials) {
    return {
      ...values,
      allCredentials: false,
      credentialIds: [...credentialIds],
    }
  }
  return values
}

function buildBatchRules(values: QuotaBatchFormValues): QuotaRuleUpsertBody[] | null {
  const lu = parseOptionalUsd(values.limit_usd)
  const ls = parseOptionalUsd(values.soft_limit_usd)
  const lt = parseOptionalInt(values.limit_tokens)
  const lr = parseOptionalInt(values.limit_requests)
  if (lu === null && lt === null && lr === null) return null

  const models = values.allModels ? [null] : values.modelNames.map((m) => m || null)
  if (!values.allModels && models.length === 0) return null

  const rules: QuotaRuleUpsertBody[] = []

  if (values.layer === 'platform') {
    const subjects: { target_kind: QuotaRuleUpsertBody['target_kind']; target_id?: string }[] = []
    if (values.subjectMode === 'tenant') {
      subjects.push({ target_kind: 'tenant' })
    } else if (values.subjectMode === 'users') {
      for (const uid of values.userIds) {
        subjects.push({ target_kind: 'user', target_id: uid })
      }
    } else {
      for (const kid of values.keyIds) {
        subjects.push({ target_kind: 'key', target_id: kid })
      }
    }
    if (subjects.length === 0) return null
    for (const sub of subjects) {
      for (const model of models) {
        const body: QuotaRuleUpsertBody = {
          layer: 'platform',
          target_kind: sub.target_kind,
          period: values.period,
        }
        if (sub.target_id) body.target_id = sub.target_id
        if (model) body.model_name = model
        if (lu !== null) body.limit_usd = lu
        if (ls !== null) body.soft_limit_usd = ls
        if (lt !== null) body.limit_tokens = lt
        if (lr !== null) body.limit_requests = lr
        rules.push(body)
      }
    }
    return rules
  }

  if (values.layer === 'upstream') {
    const creds = values.allCredentials ? [] : values.credentialIds
    if (!values.allCredentials && creds.length === 0) return null
    const credentialTargets = values.allCredentials ? [null] : creds
    const ws = parseOptionalInt(values.windowSeconds) ?? 0
    for (const credId of credentialTargets) {
      for (const model of models) {
        const body: QuotaRuleUpsertBody = {
          layer: 'upstream',
          window_seconds: ws,
          quota_label: values.quotaLabel.trim() || 'default',
        }
        if (credId) body.credential_id = credId
        if (model) body.model_name = model
        if (lu !== null) body.limit_usd = lu
        if (lt !== null) body.limit_tokens = lt
        if (lr !== null) body.limit_requests = lr
        rules.push(body)
      }
    }
    return rules
  }

  return null
}

export function useQuotaCenter() {
  const teamId = useGatewayTeamId()
  const { toast } = useToast()
  const { isPlatformViewer } = useGatewayPermission()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()

  const layerFilter = searchParams.get('layer') ?? 'all'
  const modelFilter = searchParams.get('model') ?? ''
  const periodFilter = searchParams.get('period') ?? 'all'

  const [batchOpen, setBatchOpen] = useState(false)
  const [batchValues, setBatchValues] = useState<QuotaBatchFormValues>(DEFAULT_BATCH_FORM)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const listParams = useMemo(
    () => ({
      layer: layerFilter === 'all' ? undefined : (layerFilter as QuotaRuleLayer),
      model_name: modelFilter || undefined,
      period: periodFilter === 'all' ? undefined : (periodFilter as 'daily' | 'monthly' | 'total'),
    }),
    [layerFilter, modelFilter, periodFilter]
  )

  const rulesQuery = useGatewayQuotaRules(teamId, listParams)

  const needsPickerData = batchOpen || modelFilter.trim() !== ''
  const needsLabelData = batchOpen || (rulesQuery.data?.length ?? 0) > 0

  const keysQuery = useQuery({
    queryKey: ['gateway', 'keys', teamId],
    queryFn: () => gatewayApi.listKeys(teamId),
    enabled: teamId.length > 0 && needsLabelData,
    staleTime: GATEWAY_QUOTA_META_STALE_MS,
  })

  const membersQuery = useQuery({
    queryKey: ['gateway', 'members', teamId],
    queryFn: () => gatewayApi.listMembers(teamId),
    enabled: teamId.length > 0 && needsLabelData,
    staleTime: GATEWAY_QUOTA_META_STALE_MS,
  })

  const credsQuery = useQuery({
    queryKey: ['gateway', 'credential-summaries', teamId],
    queryFn: () => gatewayApi.listCredentialSummaries(teamId),
    enabled: teamId.length > 0 && needsLabelData,
    staleTime: GATEWAY_QUOTA_META_STALE_MS,
  })

  const modelPages = useInfiniteGatewayModelPages(
    teamId,
    { registry_scope: 'callable' },
    { enabled: needsPickerData, prefetchMode: 'open' }
  )

  const routesQuery = useQuery({
    queryKey: ['gateway', 'routes', teamId],
    queryFn: () => gatewayApi.listRoutes(teamId),
    enabled: teamId.length > 0 && needsPickerData,
    staleTime: GATEWAY_MODELS_STALE_MS,
  })

  const existingModelNames = useMemo(
    () => (rulesQuery.data ?? []).map((r) => r.key.model_name),
    [rulesQuery.data]
  )

  const modelOptions = useMemo(
    () =>
      buildBudgetModelOptions({
        models: modelPages.items,
        routes: routesQuery.data ?? [],
        existingModelNames,
      }),
    [modelPages.items, routesQuery.data, existingModelNames]
  )

  const labelContext: QuotaRuleLabelContext = useMemo(() => {
    const memberLabels = new Map<string, string>()
    for (const m of membersQuery.data ?? []) {
      memberLabels.set(m.user_id, formatTeamMemberDisplay(m).primary)
    }
    const keyLabels = new Map<string, string>()
    for (const k of keysQuery.data ?? []) {
      keyLabels.set(k.id, k.name)
    }
    const credentialLabels = new Map<string, string>()
    for (const c of credsQuery.data ?? []) {
      credentialLabels.set(c.id, c.name)
    }
    return { memberLabels, keyLabels, credentialLabels }
  }, [membersQuery.data, keysQuery.data, credsQuery.data])

  const filteredItems = useMemo(() => {
    let items = rulesQuery.data ?? []
    if (periodFilter !== 'all') {
      items = items.filter(
        (r) => r.key.period === periodFilter || (r.key.period === null && periodFilter === 'total')
      )
    }
    return items
  }, [rulesQuery.data, periodFilter])

  const selectedRule = useMemo(
    () => filteredItems.find((r) => quotaRuleRowId(r) === selectedId) ?? null,
    [filteredItems, selectedId]
  )

  const batchMutation = useMutation({
    mutationFn: (rules: QuotaRuleUpsertBody[]) => gatewayApi.batchUpsertQuotaRules(teamId, rules),
    onSuccess: (result: QuotaRuleBatchUpsertResponse) => {
      void queryClient.invalidateQueries({ queryKey: ['gateway-quota-rules', teamId] })
      void queryClient.invalidateQueries({ queryKey: ['gateway-budgets', teamId] })
      if (result.failed.length > 0) {
        toast({
          title: `部分成功：${String(result.succeeded.length)} 条`,
          description: result.failed.map((f) => f.error).join('；'),
          variant: 'destructive',
        })
      } else {
        toast({ title: `已保存 ${String(result.succeeded.length)} 条配额规则` })
      }
      setBatchOpen(false)
    },
    onError: (err: Error) => {
      toast({ title: '保存失败', description: err.message, variant: 'destructive' })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (budgetId: string) => gatewayApi.deleteBudget(teamId, budgetId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: gatewayQuotaRulesQueryKey(teamId) })
      void queryClient.invalidateQueries({ queryKey: ['gateway-budgets', teamId] })
      setSelectedId(null)
      toast({ title: '已删除配额规则' })
    },
    onError: (err: Error) => {
      toast({ title: '删除失败', description: err.message, variant: 'destructive' })
    },
  })

  const setFilter = useCallback(
    (key: 'layer' | 'model' | 'period', value: string) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        if (value === '' || value === 'all') next.delete(key)
        else next.set(key, value)
        return next
      })
    },
    [setSearchParams]
  )

  const credentialOptions = useMemo(
    () => (credsQuery.data ?? []).map((c) => ({ id: c.id, label: c.name })),
    [credsQuery.data]
  )

  const credentialIds = useMemo(() => credentialOptions.map((c) => c.id), [credentialOptions])

  const resolvedBatchValues = useMemo(
    () => expandBatchFormValues(batchValues, credentialIds),
    [batchValues, credentialIds]
  )

  const batchPreviewCount = useMemo(
    () => buildBatchRules(resolvedBatchValues)?.length ?? 0,
    [resolvedBatchValues]
  )

  const memberOptions = useMemo(
    () =>
      (membersQuery.data ?? []).map((m) => ({
        id: m.user_id,
        label: formatTeamMemberDisplay(m).primary,
      })),
    [membersQuery.data]
  )

  const keyOptions = useMemo(
    () => (keysQuery.data ?? []).map((k) => ({ id: k.id, label: k.name })),
    [keysQuery.data]
  )

  const submitBatch = useCallback(() => {
    if (batchValues.layer === 'downstream') {
      toast({
        title: '下游权益',
        description: '请通过虚拟 Key 页配置下游套餐；统一批量写入即将支持。',
        variant: 'destructive',
      })
      return
    }
    const rules = buildBatchRules(resolvedBatchValues)
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
  }, [batchValues.layer, resolvedBatchValues, batchMutation, toast])

  const confirmDelete = useCallback(
    (rule: QuotaRule) => {
      const budgetId = rule.source_ref.budget_id
      if (!budgetId) {
        toast({ title: '计划类配额请至凭据/Key 页管理', variant: 'destructive' })
        return
      }
      deleteMutation.mutate(budgetId)
    },
    [deleteMutation, toast]
  )

  const selectRule = useCallback((rule: QuotaRule) => {
    setSelectedId(quotaRuleRowId(rule))
  }, [])

  const clearSelection = useCallback(() => {
    setSelectedId(null)
  }, [])

  const refresh = useCallback(() => {
    void rulesQuery.refetch()
  }, [rulesQuery])

  return {
    teamId,
    formDisabled: isPlatformViewer,
    isLoading: rulesQuery.isLoading,
    isRefreshing: rulesQuery.isFetching,
    filteredItems,
    selectedRule,
    selectedId,
    selectRule,
    clearSelection,
    labelContext,
    layerFilter,
    modelFilter,
    periodFilter,
    setFilter,
    batchOpen,
    setBatchOpen,
    batchValues,
    setBatchValues,
    submitBatch,
    batchPending: batchMutation.isPending,
    confirmDelete,
    deletePending: deleteMutation.isPending,
    refresh,
    memberOptions,
    keyOptions,
    credentialOptions,
    modelOptions,
    modelsLoading: modelPages.isLoading || routesQuery.isLoading,
    onModelPickerOpenChange: modelPages.onPickerOpenChange,
    batchPreviewCount,
  }
}

export type QuotaCenterState = ReturnType<typeof useQuotaCenter>
