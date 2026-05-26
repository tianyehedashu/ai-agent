import { useCallback, useEffect, useMemo, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import { gatewayApi, type BudgetUpsertBody, type GatewayBudget } from '@/api/gateway'
import { useInfiniteGatewayModelPages } from '@/features/gateway-models/hooks/use-infinite-gateway-model-pages'
import { GATEWAY_MODELS_STALE_MS } from '@/features/gateway-models/utils'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { formatTeamMemberDisplay } from '@/types/permissions'

import { adminTabsForPlatform, parseAdminTab, type BudgetAdminTab } from './budget-admin-constants'
import {
  buildBudgetUpsertBody,
  budgetFormValuesFromBudget,
  DEFAULT_BUDGET_FORM_VALUES,
  type BudgetFormValues,
} from './budget-form-utils'
import { buildBudgetModelOptions, type BudgetModelOption } from './budget-model-options'
import { gatewayBudgetsQueryKey } from './use-gateway-budgets'

export interface BudgetAdminWorkspaceState {
  teamId: string
  tabs: BudgetAdminTab[]
  activeTab: BudgetAdminTab
  modelFilter: string
  periodFilter: string
  createOpen: boolean
  setCreateOpen: (open: boolean) => void
  createValues: BudgetFormValues
  setCreateValues: (values: BudgetFormValues) => void
  selectedBudget: GatewayBudget | null
  editValues: BudgetFormValues | null
  setEditValues: (values: BudgetFormValues) => void
  deleteTarget: GatewayBudget | null
  setDeleteTarget: (budget: GatewayBudget | null) => void
  formDisabled: boolean
  isLoading: boolean
  filteredItems: GatewayBudget[]
  modelOptions: BudgetModelOption[]
  modelsLoading: boolean
  onModelPickerOpenChange: (open: boolean) => void
  keyOptions: { id: string; label: string }[]
  memberOptions: { id: string; label: string }[]
  upsertPending: boolean
  deletePending: boolean
  handleTabChange: (tab: string) => void
  handleModelFilterChange: (value: string) => void
  handlePeriodFilterChange: (value: string) => void
  selectBudget: (budget: GatewayBudget) => void
  clearSelection: () => void
  submitForm: (values: BudgetFormValues) => void
  confirmDelete: () => void
}

export function useBudgetAdminWorkspace(): BudgetAdminWorkspaceState {
  const teamId = useGatewayTeamId()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const { isPlatformAdmin, isPlatformViewer } = useGatewayPermission()
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab = parseAdminTab(searchParams.get('tab'), isPlatformAdmin)
  const modelFilter = searchParams.get('model') ?? ''
  const periodFilter = searchParams.get('period') ?? 'all'
  const [createOpen, setCreateOpen] = useState(false)
  const [createValues, setCreateValues] = useState<BudgetFormValues>({
    ...DEFAULT_BUDGET_FORM_VALUES,
    target_kind: activeTab === 'system' ? 'system' : activeTab,
  })
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [editValues, setEditValues] = useState<BudgetFormValues | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<GatewayBudget | null>(null)

  const formDisabled = isPlatformViewer
  const tabs = adminTabsForPlatform(isPlatformAdmin)

  const modelNameParam = modelFilter.trim() !== '' ? modelFilter.trim() : undefined

  const { data: items, isLoading } = useQuery({
    queryKey: gatewayBudgetsQueryKey(teamId, {
      target_kind: activeTab,
      model_name: modelNameParam,
    }),
    queryFn: () =>
      gatewayApi.listBudgets(teamId, {
        target_kind: activeTab,
        model_name: modelNameParam,
      }),
  })

  const { data: keys = [] } = useQuery({
    queryKey: ['gateway', 'keys', teamId],
    queryFn: () => gatewayApi.listKeys(teamId),
    enabled: activeTab === 'key' || createValues.target_kind === 'key',
  })

  const { data: members = [] } = useQuery({
    queryKey: ['gateway', 'members', teamId],
    queryFn: () => gatewayApi.listMembers(teamId),
    enabled: activeTab === 'user' || createValues.target_kind === 'user',
  })

  const needsModelOptions =
    createOpen || modelFilter.trim() !== '' || activeTab === 'tenant' || activeTab === 'system'

  const {
    items: models,
    isLoading: modelsQueryLoading,
    onPickerOpenChange: onModelPickerOpenChange,
  } = useInfiniteGatewayModelPages(
    teamId,
    { registry_scope: 'callable' },
    { enabled: needsModelOptions, prefetchMode: 'open' }
  )

  useEffect(() => {
    if (createOpen) {
      onModelPickerOpenChange(true)
    }
  }, [createOpen, onModelPickerOpenChange])

  const { data: routes = [], isLoading: routesQueryLoading } = useQuery({
    queryKey: ['gateway', 'routes', teamId],
    queryFn: () => gatewayApi.listRoutes(teamId),
    staleTime: GATEWAY_MODELS_STALE_MS,
  })

  const existingBudgetModelNames = useMemo(
    () => (items ?? []).map((budget) => budget.model_name),
    [items]
  )

  const modelOptions = useMemo(
    () =>
      buildBudgetModelOptions({
        models,
        routes,
        existingModelNames: existingBudgetModelNames,
      }),
    [models, routes, existingBudgetModelNames]
  )

  const modelsLoading = modelsQueryLoading || routesQueryLoading

  const keyOptions = useMemo(
    () =>
      keys
        .filter((k) => !k.is_system)
        .map((k) => ({
          id: k.id,
          label: k.name.trim() ? k.name : k.masked_key,
        })),
    [keys]
  )

  const memberOptions = useMemo(
    () =>
      members.map((m) => ({
        id: m.user_id,
        label: formatTeamMemberDisplay(m).primary,
      })),
    [members]
  )

  const filteredItems = useMemo(() => {
    const rows = items ?? []
    if (periodFilter === 'all') {
      return rows
    }
    return rows.filter((b) => b.period === periodFilter)
  }, [items, periodFilter])

  const selectedBudget = useMemo(
    () => (items ?? []).find((b) => b.id === selectedId) ?? null,
    [items, selectedId]
  )

  const invalidateBudgets = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ['gateway', 'budgets'] })
  }, [queryClient])

  const resetAfterSave = useCallback((): void => {
    setCreateOpen(false)
    setCreateValues({
      ...DEFAULT_BUDGET_FORM_VALUES,
      target_kind: activeTab === 'system' ? 'system' : activeTab,
    })
    setSelectedId(null)
    setEditValues(null)
  }, [activeTab])

  const upsertMutation = useMutation({
    mutationFn: (body: BudgetUpsertBody) => gatewayApi.upsertBudget(teamId, body),
    onSuccess: () => {
      invalidateBudgets()
      toast({ title: '预算已保存' })
      resetAfterSave()
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '保存失败', description: e.message })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => gatewayApi.deleteBudget(teamId, id),
    onSuccess: () => {
      invalidateBudgets()
      toast({ title: '已删除' })
      setDeleteTarget(null)
      setSelectedId(null)
      setEditValues(null)
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '删除失败', description: e.message })
    },
  })

  const handleTabChange = useCallback(
    (tab: string): void => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        next.set('tab', tab)
        return next
      })
      setSelectedId(null)
      setEditValues(null)
      setCreateValues((v) => ({
        ...v,
        target_kind: tab as BudgetFormValues['target_kind'],
        target_id: '',
      }))
    },
    [setSearchParams]
  )

  const handleModelFilterChange = useCallback(
    (value: string): void => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        if (value === '__all__') next.delete('model')
        else next.set('model', value)
        return next
      })
    },
    [setSearchParams]
  )

  const handlePeriodFilterChange = useCallback(
    (value: string): void => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        if (value === 'all') next.delete('period')
        else next.set('period', value)
        return next
      })
    },
    [setSearchParams]
  )

  const selectBudget = useCallback((budget: GatewayBudget): void => {
    setSelectedId(budget.id)
    setEditValues(budgetFormValuesFromBudget(budget))
  }, [])

  const clearSelection = useCallback((): void => {
    setSelectedId(null)
    setEditValues(null)
  }, [])

  const submitForm = useCallback(
    (values: BudgetFormValues): void => {
      const body = buildBudgetUpsertBody(values)
      if (body === null) {
        toast({
          variant: 'destructive',
          title: '请完善表单',
          description: '需选择目标并至少填写一项限额（USD / Token / 请求数）',
        })
        return
      }
      upsertMutation.mutate(body)
    },
    [toast, upsertMutation]
  )

  const confirmDelete = useCallback((): void => {
    if (deleteTarget) {
      deleteMutation.mutate(deleteTarget.id)
    }
  }, [deleteMutation, deleteTarget])

  return {
    teamId,
    tabs,
    activeTab,
    modelFilter,
    periodFilter,
    createOpen,
    setCreateOpen,
    createValues,
    setCreateValues,
    selectedBudget,
    editValues,
    setEditValues,
    deleteTarget,
    setDeleteTarget,
    formDisabled,
    isLoading,
    filteredItems,
    modelOptions,
    modelsLoading,
    onModelPickerOpenChange,
    keyOptions,
    memberOptions,
    upsertPending: upsertMutation.isPending,
    deletePending: deleteMutation.isPending,
    handleTabChange,
    handleModelFilterChange,
    handlePeriodFilterChange,
    selectBudget,
    clearSelection,
    submitForm,
    confirmDelete,
  }
}
