/**
 * 统一凭据工作区：个人 + 团队 + 系统单列表。
 */

import { Suspense, useCallback, useMemo, useRef, useState } from 'react'
import type React from 'react'

import { useMutation, useQueryClient } from '@tanstack/react-query'

import { gatewayApi, type ProviderCredential } from '@/api/gateway'
import { PaginationControls } from '@/components/pagination-controls'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { useGatewayBudgets } from '@/features/gateway-budget/use-gateway-budgets'
import { GatewayCredentialsEmptyState } from '@/features/gateway-credentials/components/gateway-credentials-empty-state'
import { GatewayCredentialsListShell } from '@/features/gateway-credentials/components/gateway-credentials-list-shell'
import { CredentialDeleteConfirmDialog } from '@/features/gateway-credentials/credential-delete-confirm-dialog'
import { invalidateCredentialProbeCache } from '@/features/gateway-credentials/credential-probe-cache'
import { useCredentialDeleteFlow } from '@/features/gateway-credentials/hooks/use-credential-delete-flow'
import type { GatewayCredentialMutations } from '@/features/gateway-credentials/hooks/use-gateway-credential-mutations'
import { useUnifiedCredentialsList } from '@/features/gateway-credentials/hooks/use-unified-credentials-list'
import { PersonalCredentialEditDialog } from '@/features/gateway-credentials/personal-credentials-panel'
import { invalidateGatewayCredentialCaches } from '@/features/gateway-credentials/query-keys'
import type { UnifiedCredentialScopeFilter } from '@/features/gateway-credentials/unified/unified-credentials-filters'
import { UnifiedCredentialsList } from '@/features/gateway-credentials/unified/unified-credentials-list'
import { UnifiedCredentialsToolbar } from '@/features/gateway-credentials/unified/unified-credentials-toolbar'
import { useInfinitePersonalModelPages } from '@/features/gateway-models/hooks/use-infinite-gateway-model-pages'
import {
  useGatewayContributorCollaborationTeams,
  useGatewayTeamNameMap,
} from '@/features/gateway-teams/use-gateway-teams'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { lazyWithReload } from '@/lib/lazy-with-reload'
import { Loader2, Plus } from '@/lib/lucide-icons'
import { buildFilterKey, usePaginationPageForFilters } from '@/lib/pagination'
import { useCurrentUser } from '@/stores/user'

const CopyCredentialsDialog = lazyWithReload(() =>
  import('@/features/gateway-credentials/copy-credentials-dialog').then((m) => ({
    default: m.CopyCredentialsDialog,
  }))
)

export interface UnifiedCredentialsWorkspaceProps {
  mutations: GatewayCredentialMutations
  onAdd: (provider?: string, teamId?: string) => void
  editPersonalCredential?: ProviderCredential | null
  onEditPersonalCredentialChange?: (credential: ProviderCredential | null) => void
  onAddModelsPersonal?: (credential: ProviderCredential) => void
}

export function UnifiedCredentialsWorkspace({
  mutations,
  onAdd,
  editPersonalCredential = null,
  onEditPersonalCredentialChange,
  onAddModelsPersonal,
}: UnifiedCredentialsWorkspaceProps): React.JSX.Element {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const routeTeamId = useGatewayTeamId()
  const currentUser = useCurrentUser()
  const viewerUserId = currentUser?.id ?? null
  const { isPlatformAdmin, canContribute } = useGatewayPermission()
  const contributorTeams = useGatewayContributorCollaborationTeams()
  const teamNameById = useGatewayTeamNameMap()

  const [search, setSearch] = useState('')
  const [scopeFilter, setScopeFilter] = useState<UnifiedCredentialScopeFilter>('all')
  const filterKey = buildFilterKey([search, scopeFilter])
  const [page, setPage] = usePaginationPageForFilters(filterKey)
  const [personalPendingDelete, setPersonalPendingDelete] = useState<ProviderCredential | null>(
    null
  )
  const [copyDialogState, setCopyDialogState] = useState<{
    open: boolean
    preselectedIds: string[]
  }>({ open: false, preselectedIds: [] })

  const {
    items,
    isLoading,
    isFetching,
    refetch,
    counts,
    filteredTotal,
    personalCredentials,
    copyableTeamCredentials,
    pagination,
  } = useUnifiedCredentialsList({ search, scopeFilter, page })
  const hasActiveFilters = scopeFilter !== 'all' || search.trim().length > 0
  const deleteFlow = useCredentialDeleteFlow(mutations, routeTeamId)
  const { data: personalBudgets = [] } = useGatewayBudgets(routeTeamId)
  const { items: myModels } = useInfinitePersonalModelPages(undefined, {
    enabled: currentUser !== null,
    prefetchMode: 'idle',
  })

  const teamById = useMemo(() => {
    const map = new Map<string, (typeof contributorTeams)[number]>()
    for (const team of contributorTeams) {
      map.set(team.id, team)
    }
    return map
  }, [contributorTeams])

  const personalCredentialsForActions = personalCredentials

  const invalidate = useCallback((): void => {
    invalidateGatewayCredentialCaches(queryClient, {
      teamId: routeTeamId,
      includeModels: true,
      includeBudgets: true,
    })
  }, [queryClient, routeTeamId])

  const personalDeleteMutation = useMutation({
    mutationFn: gatewayApi.deleteMyCredential,
    onSuccess: (_data, credentialId) => {
      invalidateCredentialProbeCache(queryClient, 'user', credentialId)
      invalidate()
      setPersonalPendingDelete(null)
      if (editPersonalCredential?.id === credentialId) {
        onEditPersonalCredentialChange?.(null)
      }
      toast({ title: '凭据已删除', description: '关联的个人注册模型已一并移除' })
    },
    onError: (e: Error) => {
      setPersonalPendingDelete(null)
      toast({ variant: 'destructive', title: '删除失败', description: e.message })
    },
  })

  const personalDeleteRef = useRef<ProviderCredential | null>(null)
  personalDeleteRef.current = personalPendingDelete

  const testMutation = useMutation({
    mutationFn: (credentialId: string) => gatewayApi.probeMyCredential(credentialId),
    onSuccess: (data) => {
      if (data.support !== 'error') toast({ title: 'Key 有效' })
      else {
        toast({
          variant: 'destructive',
          title: 'Key 验证失败',
          description: data.message ?? '上游探测失败',
        })
      }
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '验证失败', description: e.message })
    },
  })

  const handleDelete = useCallback(
    (credential: ProviderCredential): void => {
      if (credential.scope === 'user') {
        setPersonalPendingDelete(credential)
        return
      }
      deleteFlow.handleDeleteCredential(credential)
    },
    [deleteFlow]
  )

  const handlePersonalDeleteConfirm = useCallback((): void => {
    const pending = personalDeleteRef.current
    if (pending) {
      personalDeleteMutation.mutate(pending.id)
    }
  }, [personalDeleteMutation])

  const hasCopyableSource = counts.personal > 0 || copyableTeamCredentials.length > 0
  const hasCopyDestination = contributorTeams.length > 0 || copyableTeamCredentials.length > 0
  const showCopy = canContribute && hasCopyableSource && hasCopyDestination

  const toolbar = (
    <UnifiedCredentialsToolbar
      search={search}
      onSearchChange={setSearch}
      scopeFilter={scopeFilter}
      onScopeFilterChange={setScopeFilter}
      counts={counts}
      filteredTotal={filteredTotal}
      hasActiveFilters={hasActiveFilters}
      isRefreshing={isFetching}
      onRefresh={() => {
        void refetch()
      }}
      showCopy={showCopy}
      onCopy={() => {
        setCopyDialogState({ open: true, preselectedIds: [] })
      }}
      showVerify={counts.personal > 0}
      verifyPending={testMutation.isPending}
      onVerify={() => {
        const active =
          personalCredentialsForActions.find((row) => row.is_active) ??
          personalCredentialsForActions[0]
        testMutation.mutate(active.id)
      }}
      onAdd={() => {
        onAdd()
      }}
    />
  )

  const paginationSlot =
    pagination.total > pagination.page_size ? (
      <PaginationControls
        page={pagination.page}
        page_size={pagination.page_size}
        total={pagination.total}
        has_next={pagination.has_next}
        has_prev={pagination.has_prev}
        onPageChange={setPage}
      />
    ) : null

  if (!currentUser) {
    return (
      <GatewayCredentialsEmptyState
        title="请先登录"
        description="登录后可管理个人、团队与系统凭据。"
      />
    )
  }

  return (
    <>
      <GatewayCredentialsListShell
        hintSlot="同一列表查看个人 BYOK、协作团队与系统凭据；「归属」列标明所属范围。"
        toolbar={toolbar}
        emptySlot={
          <GatewayCredentialsEmptyState
            title="暂无凭据"
            description="添加个人或团队凭据后即可注册模型。"
            action={
              <Button
                size="sm"
                onClick={() => {
                  onAdd()
                }}
              >
                <Plus className="mr-1.5 h-4 w-4" />
                新增
              </Button>
            }
          />
        }
        isLoading={isLoading}
        isEmpty={!isLoading && counts.total === 0}
        paginationSlot={paginationSlot ?? undefined}
      >
        {counts.total > 0 ? (
          <UnifiedCredentialsList
            items={items}
            filteredTotal={filteredTotal}
            hasActiveFilters={hasActiveFilters}
            routeTeamId={routeTeamId}
            teamById={teamById}
            teamNameById={teamNameById}
            viewerUserId={viewerUserId}
            isPlatformAdmin={isPlatformAdmin}
            personalDeletePending={personalDeleteMutation.isPending}
            updateMutation={mutations.updateMutation}
            onEditPersonal={(credential) => {
              onEditPersonalCredentialChange?.(credential)
            }}
            onAddModelsPersonal={onAddModelsPersonal}
            onDelete={handleDelete}
          />
        ) : null}
      </GatewayCredentialsListShell>

      <Dialog
        open={editPersonalCredential !== null}
        onOpenChange={(open) => {
          if (!open) onEditPersonalCredentialChange?.(null)
        }}
      >
        {editPersonalCredential && currentUser.id ? (
          <PersonalCredentialEditDialog
            key={editPersonalCredential.id}
            cred={editPersonalCredential}
            userId={currentUser.id}
            personalBudgets={personalBudgets}
            myModels={myModels}
            onClose={() => {
              onEditPersonalCredentialChange?.(null)
            }}
            onSaved={() => {
              invalidateCredentialProbeCache(queryClient, 'user', editPersonalCredential.id)
              invalidate()
              onEditPersonalCredentialChange?.(null)
            }}
          />
        ) : null}
      </Dialog>

      <CredentialDeleteConfirmDialog
        credential={deleteFlow.credentialPendingDelete}
        isPending={deleteFlow.isDeletePending}
        onOpenChange={deleteFlow.handleDeleteDialogOpenChange}
        onConfirm={deleteFlow.handleDeleteConfirm}
      />

      <CredentialDeleteConfirmDialog
        credential={personalPendingDelete}
        isPending={personalDeleteMutation.isPending}
        variant="personal"
        onOpenChange={(open) => {
          if (!open) setPersonalPendingDelete(null)
        }}
        onConfirm={handlePersonalDeleteConfirm}
      />

      <Suspense
        fallback={
          <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            加载复制…
          </div>
        }
      >
        <CopyCredentialsDialog
          open={copyDialogState.open}
          onOpenChange={(next) => {
            setCopyDialogState((prev) => ({ ...prev, open: next }))
          }}
          preselectedCredentialIds={copyDialogState.preselectedIds}
          personalCredentials={[...personalCredentialsForActions]}
          teamCredentials={copyableTeamCredentials}
          teamCredentialsLoading={isLoading}
          contributorTeams={contributorTeams}
          teamNameById={teamNameById}
        />
      </Suspense>
    </>
  )
}
