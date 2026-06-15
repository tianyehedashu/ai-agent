import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import {
  gatewayApi,
  fetchAllManagedTeamModelPages,
  fetchAllPersonalGatewayModels,
  type QuotaRule,
  type QuotaRuleLayer,
  type QuotaRuleUpsertBody,
} from '@/api/gateway'
import type { GatewayModel } from '@/api/gateway/models'
import type { PersonalGatewayModel } from '@/api/gateway/my-models'
import {
  collectQuotaBatchTargetTeamIds,
  filterMemberSelfServiceCredentialSummaries,
  filterPlatformQuotaCredentialSummaries,
  filterUpstreamQuotaCredentialSummaries,
  useActorCredentialSummaries,
} from '@/features/gateway-credentials/hooks/use-actor-credential-summaries'
import { useGatewayVirtualKeys } from '@/features/gateway-keys/use-gateway-virtual-keys'
import { useGatewayRoutes } from '@/features/gateway-models/hooks/use-gateway-routes'
import { useInfiniteGatewayModelPages } from '@/features/gateway-models/hooks/use-infinite-gateway-model-pages'
import { GATEWAY_MODELS_STALE_MS } from '@/features/gateway-models/utils'
import { useGatewayTeamMembers } from '@/features/gateway-teams/use-gateway-team-members'
import { useGatewayWritableTeams } from '@/features/gateway-teams/use-gateway-teams'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId, useGatewayTeamRecord } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { useCurrentUser } from '@/stores/user'
import { formatTeamMemberDisplay } from '@/types/permissions'

import {
  buildBudgetModelOptions,
  buildUpstreamQuotaModelOptions,
  upstreamQuotaModelOptionLabel,
  type BudgetModelOption,
} from './budget-model-options'
import {
  DEFAULT_BATCH_FORM,
  expandBatchFormValues,
  type QuotaBatchFormValues,
} from './quota-batch-form'
import { quotaRuleToBatchFormValues, type EditingRuleInfo } from './quota-batch-from-rule'
import { buildBatchRules } from './quota-batch-rules'
import { executeQuotaBatchUpsert } from './quota-batch-upsert'
import { quotaRuleRowId, type QuotaRuleLabelContext } from './quota-rule-utils'
import { gatewayBudgetsBaseQueryKey } from './use-gateway-budgets'
import {
  GATEWAY_QUOTA_META_STALE_MS,
  gatewayQuotaRulesBaseQueryKey,
  gatewayQuotaRulesQueryKey,
  useGatewayQuotaRules,
} from './use-gateway-quota-rules'

export type { QuotaBatchFormValues } from './quota-batch-form'
export {
  DEFAULT_BATCH_FORM,
  patchQuotaBatchFormForLayer,
  patchQuotaBatchFormForSubjectMode,
} from './quota-batch-form'
export { buildBatchRules } from './quota-batch-rules'

export type QuotaCenterMode = 'admin' | 'member'

export interface QuotaCenterState {
  teamId: string
  teamName: string
  mode: QuotaCenterMode
  formDisabled: boolean
  isLoading: boolean
  isRefreshing: boolean
  listLoadError: string | null
  filteredItems: QuotaRule[]
  selectedRule: QuotaRule | null
  selectedId: string | null
  selectRule: (rule: QuotaRule) => void
  clearSelection: () => void
  labelContext: QuotaRuleLabelContext
  layerFilter: string
  modelFilter: string
  periodFilter: string
  setFilter: (key: 'layer' | 'model' | 'period', value: string) => void
  batchOpen: boolean
  setBatchOpen: (open: boolean) => void
  batchValues: QuotaBatchFormValues
  setBatchValues: (values: QuotaBatchFormValues) => void
  submitBatch: () => void
  batchPending: boolean
  confirmDelete: (rule: QuotaRule) => void
  confirmBatchDelete: (rules: QuotaRule[]) => Promise<void>
  deletePending: boolean
  refresh: () => void
  memberOptions: { id: string; label: string }[]
  keyOptions: { id: string; label: string }[]
  credentialOptions: {
    id: string
    label: string
    provider: string
    scope: string | null
    isLegacy?: boolean
  }[]
  metaLoading: boolean
  modelOptions: BudgetModelOption[]
  /** 批量向导内模型下拉（上游层按所选凭据过滤 real_model） */
  batchModelOptions: BudgetModelOption[]
  modelsLoading: boolean
  batchModelsLoading: boolean
  batchModelOptionMetaLabel?: (option: BudgetModelOption) => string
  onModelPickerOpenChange?: (open: boolean) => void
  batchPreviewCount: number
  /** 当前处于编辑状态的规则信息；null 表示创建/批量模式 */
  editingRuleId: string | null
  onEditRule: (rule: QuotaRule) => void
  /** 编辑模式下删除当前规则并关闭向导 */
  deleteEditingRule: () => void
}

function useQuotaCenterImpl(): QuotaCenterState {
  const teamId = useGatewayTeamId()
  const teamRecord = useGatewayTeamRecord(teamId)
  const { toast } = useToast()
  const { isAdmin, isPlatformViewer, isPlatformAdmin } = useGatewayPermission()
  const currentUser = useCurrentUser()
  const selfUserId = currentUser?.id ?? null
  const mode: QuotaCenterMode = isAdmin ? 'admin' : 'member'
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()

  const layerFilter = searchParams.get('layer') ?? 'all'
  const modelFilter = searchParams.get('model') ?? ''
  const periodFilter = searchParams.get('period') ?? 'all'
  // 成员自助：从凭据详情「设置我的限额 →」带入的凭据预填，用于预加载凭据元数据并自动开抽屉。
  const credentialPrefill = mode === 'member' ? searchParams.get('credential_id') : null
  // 管理员：统计页「设配额」/ 凭据详情跳转带入的成员、凭据预填。
  const userPrefill = mode === 'admin' ? searchParams.get('user_id') : null
  const adminCredentialPrefill = mode === 'admin' ? searchParams.get('credential_id') : null

  const [batchOpen, setBatchOpen] = useState(false)
  const [batchValues, setBatchValues] = useState<QuotaBatchFormValues>(DEFAULT_BATCH_FORM)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null)
  const editingInfoRef = useRef<EditingRuleInfo | null>(null)

  const listParams = useMemo(
    () => ({
      layer: layerFilter === 'all' ? undefined : (layerFilter as QuotaRuleLayer),
      model_name: modelFilter || undefined,
      period: periodFilter === 'all' ? undefined : (periodFilter as 'daily' | 'monthly' | 'total'),
      include_usage: true,
    }),
    [layerFilter, modelFilter, periodFilter]
  )

  const rulesQuery = useGatewayQuotaRules(teamId, listParams)

  const needsPickerData = batchOpen || modelFilter.trim() !== ''
  const needsLabelData =
    batchOpen || (rulesQuery.data?.length ?? 0) > 0 || credentialPrefill !== null || isAdmin

  const keysQuery = useGatewayVirtualKeys(teamId, {
    enabled: teamId.length > 0 && needsLabelData,
    staleTime: GATEWAY_QUOTA_META_STALE_MS,
  })

  const membersQuery = useGatewayTeamMembers(teamId)

  const writableTeams = useGatewayWritableTeams(needsLabelData)
  const adminTeamIds = useMemo(() => new Set(writableTeams.map((team) => team.id)), [writableTeams])

  const actorCredentials = useActorCredentialSummaries({ enabled: needsLabelData })

  const modelPages = useInfiniteGatewayModelPages(
    teamId,
    { registry_scope: 'callable' },
    { enabled: needsPickerData, prefetchMode: 'open' }
  )

  const routesQuery = useGatewayRoutes(teamId, {
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
    for (const c of actorCredentials.list) {
      credentialLabels.set(c.id, c.name)
    }
    return { memberLabels, keyLabels, credentialLabels }
  }, [membersQuery.data, keysQuery.data, actorCredentials.list])

  // 周期等筛选由后端 list 参数完成（滚动窗口型 upstream/downstream 规则的保留规则在服务端），
  // 此处不再二次过滤，避免与服务端语义不一致导致规则"消失"。
  const filteredItems = useMemo(() => rulesQuery.data ?? [], [rulesQuery.data])

  const selectedRule = useMemo(
    () => filteredItems.find((r) => quotaRuleRowId(r) === selectedId) ?? null,
    [filteredItems, selectedId]
  )

  const batchMutation = useMutation({
    mutationFn: (rules: QuotaRuleUpsertBody[]) =>
      executeQuotaBatchUpsert(teamId, rules, actorCredentials.contextTeamIdByCredentialId, mode),
    onSuccess: (result, rules) => {
      const targetTeamIds = collectQuotaBatchTargetTeamIds(
        teamId,
        rules,
        actorCredentials.contextTeamIdByCredentialId
      )
      for (const targetTeamId of targetTeamIds) {
        void queryClient.invalidateQueries({
          queryKey: gatewayQuotaRulesBaseQueryKey(targetTeamId),
        })
        void queryClient.invalidateQueries({ queryKey: gatewayBudgetsBaseQueryKey(targetTeamId) })
      }
      void queryClient.refetchQueries({ queryKey: gatewayQuotaRulesQueryKey(teamId, listParams) })
      if (result.succeeded.length === 0 && result.failed.length === 0) {
        toast({
          title: '未写入任何配额规则',
          description: '请检查表单并重试；若持续失败请联系管理员查看后端日志。',
          variant: 'destructive',
        })
      } else if (result.failed.length > 0) {
        toast({
          title: `部分成功：${String(result.succeeded.length)} 条`,
          description: result.failed.map((f) => f.error).join('；'),
          variant: 'destructive',
        })
      } else {
        toast({ title: `已保存 ${String(result.succeeded.length)} 条配额规则` })
      }
      handleSetBatchOpen(false)
    },
    onError: (err: Error) => {
      toast({ title: '保存失败', description: err.message, variant: 'destructive' })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (budgetId: string) =>
      mode === 'member'
        ? gatewayApi.deleteSelfQuotaRule(teamId, budgetId)
        : gatewayApi.deleteBudget(teamId, budgetId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: gatewayQuotaRulesBaseQueryKey(teamId) })
      void queryClient.invalidateQueries({ queryKey: gatewayBudgetsBaseQueryKey(teamId) })
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

  const pickerCredentials = useMemo(() => {
    const raw = actorCredentials.list
    if (mode === 'member') {
      return filterMemberSelfServiceCredentialSummaries(raw, teamId, batchValues.layer)
    }
    if (batchValues.layer === 'upstream') {
      return filterUpstreamQuotaCredentialSummaries(raw, adminTeamIds, isPlatformAdmin)
    }
    return filterPlatformQuotaCredentialSummaries(raw, teamId, isPlatformAdmin)
  }, [actorCredentials.list, mode, batchValues.layer, teamId, adminTeamIds, isPlatformAdmin])

  const credentialOptions = useMemo(() => {
    return pickerCredentials.map((c) => ({
      id: c.id,
      label: c.name,
      provider: c.provider,
      scope: c.scope,
      isLegacy:
        c.scope === 'team' && (c.created_by_user_id === null || c.created_by_user_id === undefined),
    }))
  }, [pickerCredentials])

  const pickerCredentialIds = useMemo(() => credentialOptions.map((c) => c.id), [credentialOptions])

  const resolvedBatchValues = useMemo(
    () => expandBatchFormValues(batchValues, pickerCredentialIds),
    [batchValues, pickerCredentialIds]
  )

  const upstreamCredentialIds = useMemo(
    () => (batchValues.layer === 'upstream' ? resolvedBatchValues.credentialIds : []),
    [batchValues.layer, resolvedBatchValues.credentialIds]
  )

  const memberUpstreamMode = mode === 'member' && batchValues.layer === 'upstream'

  const upstreamTeamModelsQuery = useQuery({
    queryKey: [
      'gateway',
      'quota-batch',
      'upstream-models',
      upstreamCredentialIds.slice().sort().join('|'),
    ],
    queryFn: () => fetchAllManagedTeamModelPages(),
    enabled:
      batchOpen &&
      batchValues.layer === 'upstream' &&
      !memberUpstreamMode &&
      upstreamCredentialIds.length > 0,
    staleTime: GATEWAY_MODELS_STALE_MS,
  })

  const upstreamPersonalModelsQuery = useQuery({
    queryKey: [
      'gateway',
      'quota-batch',
      'upstream-personal-models',
      upstreamCredentialIds.slice().sort().join('|'),
    ],
    queryFn: () => fetchAllPersonalGatewayModels(),
    enabled:
      batchOpen &&
      batchValues.layer === 'upstream' &&
      memberUpstreamMode &&
      upstreamCredentialIds.length > 0,
    staleTime: GATEWAY_MODELS_STALE_MS,
  })

  const upstreamTeamModelsForSelection = useMemo((): GatewayModel[] => {
    if (memberUpstreamMode) return []
    const credSet = new Set(upstreamCredentialIds)
    return (upstreamTeamModelsQuery.data ?? []).filter((model) => credSet.has(model.credential_id))
  }, [memberUpstreamMode, upstreamCredentialIds, upstreamTeamModelsQuery.data])

  const upstreamPersonalModelsForSelection = useMemo((): PersonalGatewayModel[] => {
    if (!memberUpstreamMode) return []
    const credSet = new Set(upstreamCredentialIds)
    return (upstreamPersonalModelsQuery.data ?? []).filter((model) =>
      credSet.has(model.credential_id)
    )
  }, [memberUpstreamMode, upstreamCredentialIds, upstreamPersonalModelsQuery.data])

  const upstreamModelAliasByReal = useMemo(() => {
    const map = new Map<string, string>()
    for (const model of upstreamTeamModelsForSelection) {
      const realModel = model.real_model.trim()
      if (!realModel || map.has(realModel)) continue
      map.set(realModel, model.name)
    }
    for (const model of upstreamPersonalModelsForSelection) {
      const realModel = model.model_id.trim()
      if (!realModel || map.has(realModel)) continue
      map.set(realModel, model.name)
    }
    return map
  }, [upstreamPersonalModelsForSelection, upstreamTeamModelsForSelection])

  const batchModelOptions = useMemo(() => {
    if (batchValues.layer !== 'upstream') {
      return modelOptions
    }
    return buildUpstreamQuotaModelOptions({
      models: upstreamTeamModelsForSelection,
      personalModels: upstreamPersonalModelsForSelection,
      credentialIds: upstreamCredentialIds,
      existingModelNames,
    })
  }, [
    batchValues.layer,
    existingModelNames,
    modelOptions,
    upstreamCredentialIds,
    upstreamPersonalModelsForSelection,
    upstreamTeamModelsForSelection,
  ])

  const batchModelOptionMetaLabel = useMemo(():
    | ((option: BudgetModelOption) => string)
    | undefined => {
    if (batchValues.layer !== 'upstream') return undefined
    return (option: BudgetModelOption): string =>
      upstreamQuotaModelOptionLabel(option, upstreamModelAliasByReal)
  }, [batchValues.layer, upstreamModelAliasByReal])

  const prevUpstreamCredentialKeyRef = useRef('')
  useEffect(() => {
    if (batchValues.layer !== 'upstream') {
      prevUpstreamCredentialKeyRef.current = ''
      return
    }
    const key = upstreamCredentialIds.slice().sort().join('|')
    if (prevUpstreamCredentialKeyRef.current === key) return
    prevUpstreamCredentialKeyRef.current = key
    if (batchValues.allModels || batchValues.modelNames.length === 0) return
    const valid = new Set(batchModelOptions.map((option) => option.name))
    const pruned = batchValues.modelNames.filter((name) => valid.has(name))
    if (pruned.length === batchValues.modelNames.length) return
    setBatchValues((values) => ({ ...values, modelNames: pruned }))
  }, [
    batchModelOptions,
    batchValues.allModels,
    batchValues.layer,
    batchValues.modelNames,
    upstreamCredentialIds,
  ])

  const batchPreviewCount = useMemo(() => {
    let v = resolvedBatchValues
    if (mode === 'member') {
      const layer = resolvedBatchValues.layer === 'upstream' ? 'upstream' : 'platform'
      v = {
        ...resolvedBatchValues,
        layer,
        subjectMode: layer === 'platform' ? 'users' : resolvedBatchValues.subjectMode,
        userIds: layer === 'platform' && selfUserId !== null ? [selfUserId] : [],
        keyIds: [],
      }
    }
    return buildBatchRules(v)?.length ?? 0
  }, [resolvedBatchValues, mode, selfUserId])

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
    let formValues = resolvedBatchValues
    // 编辑模式：保留原始维度，仅改限额与模型
    if (editingRuleId && editingInfoRef.current) {
      formValues = resolvedBatchValues
      // 不强制覆盖为成员自助锁定
    } else if (mode === 'member') {
      if (selfUserId === null) {
        toast({ title: '无法识别当前用户', variant: 'destructive' })
        return
      }
      const layer = resolvedBatchValues.layer === 'upstream' ? 'upstream' : 'platform'
      if (resolvedBatchValues.credentialIds.length === 0) {
        toast({
          title: '请选择凭据',
          description:
            layer === 'upstream'
              ? '请选择本人的 BYOK 凭据。'
              : '自助配额须选择至少一个凭据。如列表为空，请先在凭据页添加团队凭据，或联系管理员。',
          variant: 'destructive',
        })
        return
      }
      formValues = {
        ...resolvedBatchValues,
        layer,
        subjectMode: layer === 'platform' ? 'users' : resolvedBatchValues.subjectMode,
        userIds: layer === 'platform' ? [selfUserId] : [],
        keyIds: [],
      }
    } else if (editingRuleId) {
      // 编辑模式兜底：若校验通过且非 member/admin 兜底路径，
      // 直接按表单值提交（维度已锁定，仅限额变更）。
      formValues = resolvedBatchValues
    }
    const rules = buildBatchRules(formValues)
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
  }, [resolvedBatchValues, batchMutation, toast, mode, selfUserId, editingRuleId])

  const confirmDelete = useCallback(
    (rule: QuotaRule) => {
      const budgetId = rule.source_ref.budget_id
      if (!budgetId) {
        toast({ title: '计划类配额请至凭据/Key 页管理', variant: 'destructive' })
        return
      }
      // P11: 删除确认 — 直接执行删除，由调用方展示确认对话框
      deleteMutation.mutate(budgetId)
    },
    [deleteMutation, toast]
  )

  /** 编辑模式下删除当前规则 */
  const deleteEditingRule = useCallback(() => {
    if (!editingRuleId) return
    const budgetId = editingRuleId
    deleteMutation.mutate(budgetId, {
      onSuccess: () => {
        setBatchOpen(false)
      },
    })
  }, [editingRuleId, deleteMutation])

  const confirmBatchDelete = useCallback(
    async (rules: QuotaRule[]) => {
      const deletable = rules.filter((r) => r.source_ref.budget_id !== null)
      if (deletable.length === 0) {
        toast({
          title: '所选规则均不可删除（计划类配额请至凭据/Key 页管理）',
          variant: 'destructive',
        })
        return
      }
      const results = await Promise.allSettled(
        deletable.map((r) => {
          const budgetId = r.source_ref.budget_id
          // deletable 已过滤 budget_id !== null，此处安全断言
          return deleteMutation.mutateAsync(budgetId as string)
        })
      )
      const succeeded = results.filter((r) => r.status === 'fulfilled').length
      const failed = results.filter((r) => r.status === 'rejected').length
      if (failed > 0) {
        toast({
          title: `批量删除完成：${String(succeeded)} 条成功，${String(failed)} 条失败`,
          variant: failed === deletable.length ? 'destructive' : 'default',
        })
      } else {
        toast({ title: `已删除 ${String(succeeded)} 条配额规则` })
      }
    },
    [deleteMutation, toast]
  )

  // 成员自助：从凭据详情「设置我的限额 →」跳转时，待 owned 凭据加载后预填并自动开抽屉。
  const consumedPrefillRef = useRef<string | null>(null)
  useEffect(() => {
    if (credentialPrefill === null) return
    if (consumedPrefillRef.current === credentialPrefill) return
    if (!credentialOptions.some((c) => c.id === credentialPrefill)) return
    consumedPrefillRef.current = credentialPrefill
    setBatchValues({
      ...DEFAULT_BATCH_FORM,
      subjectMode: 'users',
      credentialIds: [credentialPrefill],
      allModels: modelFilter.trim() === '',
      modelNames: modelFilter.trim() === '' ? [] : [modelFilter.trim()],
    })
    setBatchOpen(true)
  }, [credentialPrefill, modelFilter, credentialOptions])

  // 管理员：统计页「设配额」（user_id）/ 凭据详情（credential_id + layer=upstream）跳转预填并自动开抽屉。
  const consumedAdminPrefillRef = useRef<string | null>(null)
  useEffect(() => {
    if (mode !== 'admin') return
    if (userPrefill === null && adminCredentialPrefill === null) return
    if (actorCredentials.isLoading) return
    const token = `${userPrefill ?? ''}|${adminCredentialPrefill ?? ''}`
    if (consumedAdminPrefillRef.current === token) return
    if (
      adminCredentialPrefill !== null &&
      userPrefill === null &&
      !pickerCredentials.some((c) => c.id === adminCredentialPrefill)
    ) {
      consumedAdminPrefillRef.current = token
      toast({
        title: '无法预填凭据',
        description: '该凭据不在你可管理的上游配额范围内，或尚未加载完成。',
        variant: 'destructive',
      })
      return
    }
    consumedAdminPrefillRef.current = token
    const model = modelFilter.trim()
    const modelFields = {
      allModels: model === '',
      modelNames: model === '' ? [] : [model],
    }
    if (userPrefill !== null) {
      setBatchValues({
        ...DEFAULT_BATCH_FORM,
        subjectMode: 'users',
        userIds: [userPrefill],
        credentialIds: adminCredentialPrefill ? [adminCredentialPrefill] : [],
        ...modelFields,
      })
    } else if (adminCredentialPrefill !== null) {
      // 仅凭据无成员：platform 层凭据维度必须挂在成员上，故落到 upstream 层。
      setBatchValues({
        ...DEFAULT_BATCH_FORM,
        layer: 'upstream',
        allCredentials: false,
        credentialIds: [adminCredentialPrefill],
        ...modelFields,
      })
    }
    setBatchOpen(true)
  }, [
    mode,
    userPrefill,
    adminCredentialPrefill,
    modelFilter,
    actorCredentials.isLoading,
    pickerCredentials,
    toast,
  ])

  const selectRule = useCallback((rule: QuotaRule) => {
    setSelectedId(quotaRuleRowId(rule))
  }, [])

  const clearSelection = useCallback(() => {
    setSelectedId(null)
  }, [])

  const onEditRule = useCallback(
    (rule: QuotaRule) => {
      const parsed = quotaRuleToBatchFormValues(rule)
      if (!parsed) {
        toast({
          title: '暂不支持编辑此规则',
          description: '上游/下游配额及计划类规则请在凭据/Key 页管理。',
          variant: 'destructive',
        })
        return
      }
      editingInfoRef.current = parsed.info
      setEditingRuleId(parsed.info.budgetId)
      setBatchValues(parsed.values)
      setBatchOpen(true)
    },
    [toast]
  )

  const handleSetBatchOpen = useCallback((open: boolean) => {
    setBatchOpen(open)
    if (!open) {
      setEditingRuleId(null)
      editingInfoRef.current = null
    }
  }, [])

  const refresh = useCallback(() => {
    void rulesQuery.refetch()
  }, [rulesQuery])

  const listLoadError = useMemo((): string | null => {
    if (!rulesQuery.isError) return null
    const err = rulesQuery.error
    return err instanceof Error ? err.message : '加载配额规则失败'
  }, [rulesQuery.isError, rulesQuery.error])

  return {
    teamId,
    teamName: teamRecord?.name ?? teamId.slice(0, 8),
    mode,
    // 平台只读账号全站不可写；成员模式下若无法识别本人则禁用自助写入。
    formDisabled: isPlatformViewer || (mode === 'member' && selfUserId === null),
    isLoading: rulesQuery.isLoading,
    isRefreshing: rulesQuery.isFetching,
    listLoadError,
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
    setBatchOpen: handleSetBatchOpen,
    batchValues,
    setBatchValues,
    submitBatch,
    batchPending: batchMutation.isPending,
    confirmDelete,
    confirmBatchDelete,
    deletePending: deleteMutation.isPending,
    refresh,
    memberOptions,
    keyOptions,
    credentialOptions,
    metaLoading:
      batchOpen && (membersQuery.isLoading || keysQuery.isLoading || actorCredentials.isLoading),
    modelOptions,
    batchModelOptions,
    modelsLoading: modelPages.isLoading || routesQuery.isLoading,
    batchModelsLoading:
      batchValues.layer === 'upstream'
        ? memberUpstreamMode
          ? upstreamPersonalModelsQuery.isLoading
          : upstreamTeamModelsQuery.isLoading
        : modelPages.isLoading || routesQuery.isLoading,
    batchModelOptionMetaLabel,
    onModelPickerOpenChange: modelPages.onPickerOpenChange,
    batchPreviewCount,
    editingRuleId,
    onEditRule,
    deleteEditingRule,
  }
}

export function useQuotaCenter(): QuotaCenterState {
  return useQuotaCenterImpl()
}
