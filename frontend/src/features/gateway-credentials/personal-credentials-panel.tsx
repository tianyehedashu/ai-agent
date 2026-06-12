/**
 * 个人凭据（/my-credentials）列表与编辑，用于 AI Gateway 凭据页「个人」Tab。
 */

import { Suspense, useCallback, useMemo, useRef, useState } from 'react'
import type React from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  gatewayApi,
  type GatewayCredentialUpdateBody,
  type PersonalGatewayModel,
  type ProviderCredential,
} from '@/api/gateway'
import type { GatewayBudget } from '@/api/gateway/budgets'
import type { GatewayTeam } from '@/api/gateway/teams'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { PersonalCredentialBudgetInline } from '@/features/gateway-budget/personal-credential-budget-inline'
import { useGatewayBudgets } from '@/features/gateway-budget/use-gateway-budgets'
import { GatewayCredentialsEmptyState } from '@/features/gateway-credentials/components/gateway-credentials-empty-state'
import { GatewayCredentialsListShell } from '@/features/gateway-credentials/components/gateway-credentials-list-shell'
import { PersonalCredentialsList } from '@/features/gateway-credentials/personal/personal-credentials-list'
import { useInfinitePersonalModelPages } from '@/features/gateway-models/hooks/use-infinite-gateway-model-pages'
import { combineFetching } from '@/features/gateway-shared/combine-fetching'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { lazyWithReload } from '@/lib/lazy-with-reload'
import { Loader2, Plus, Upload } from '@/lib/lucide-icons'
import { useCurrentUser } from '@/stores/user'

import { USER_GATEWAY_CREDENTIAL_PROVIDER_IDS } from './constants'
import { CredentialDeleteConfirmDialog } from './credential-delete-confirm-dialog'
import { CredentialEditFields } from './credential-edit-fields'
import { invalidateCredentialProbeCache } from './credential-probe-cache'
import { useProviderProfilesCatalog } from './hooks/use-provider-profiles-catalog'
import { invalidateGatewayCredentialCaches } from './query-keys'
import { useCredentialEditForm } from './use-credential-edit-form'

const ImportToTeamDialog = lazyWithReload(() =>
  import('./import-to-team-dialog').then((m) => ({ default: m.ImportToTeamDialog }))
)

export interface PersonalCredentialsPanelProps {
  onAddCredential?: (provider?: string) => void
  onAddModels?: (credential: ProviderCredential) => void
  editCredential?: ProviderCredential | null
  onEditCredentialChange?: (credential: ProviderCredential | null) => void
  highlightCredentialId?: string
  writableTeams?: GatewayTeam[]
}

export function PersonalCredentialsPanel({
  onAddCredential,
  onAddModels,
  editCredential = null,
  onEditCredentialChange,
  writableTeams = [],
}: PersonalCredentialsPanelProps = {}): React.ReactElement {
  useProviderProfilesCatalog()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const currentUser = useCurrentUser()
  const hasAuthSession = currentUser !== null
  const teamId = useGatewayTeamId()
  const [credentialPendingDelete, setCredentialPendingDelete] = useState<ProviderCredential | null>(
    null
  )
  const [importDialogState, setImportDialogState] = useState<{
    open: boolean
    preselectedIds: string[]
  }>({ open: false, preselectedIds: [] })

  const {
    data: credentials = [],
    isLoading,
    isFetching,
    refetch: refetchCredentials,
  } = useQuery({
    queryKey: ['gateway', 'my-credentials'],
    queryFn: () => gatewayApi.listMyCredentials(),
    enabled: hasAuthSession,
  })
  const {
    data: personalBudgets = [],
    isFetching: budgetsFetching,
    refetch: refetchBudgets,
  } = useGatewayBudgets(teamId)
  const { items: myModels } = useInfinitePersonalModelPages(undefined, {
    enabled: hasAuthSession,
    prefetchMode: 'idle',
  })

  const providerCount = useMemo(() => {
    return new Set(credentials.map((c) => c.provider)).size
  }, [credentials])

  const sortedCredentials = useMemo(() => {
    const providerOrder = new Map(
      USER_GATEWAY_CREDENTIAL_PROVIDER_IDS.map((id, index) => [id, index])
    )
    return [...credentials].sort((a, b) => {
      const providerDiff =
        (providerOrder.get(a.provider) ?? Number.MAX_SAFE_INTEGER) -
        (providerOrder.get(b.provider) ?? Number.MAX_SAFE_INTEGER)
      if (providerDiff !== 0) return providerDiff
      return a.name.localeCompare(b.name)
    })
  }, [credentials])

  const invalidate = useCallback((): void => {
    invalidateGatewayCredentialCaches(queryClient, {
      teamId,
      includeModels: true,
      includeBudgets: true,
    })
  }, [queryClient, teamId])

  const handleRefresh = useCallback((): void => {
    void Promise.all([refetchCredentials(), refetchBudgets()])
    invalidateGatewayCredentialCaches(queryClient, { teamId, includeModels: true })
  }, [queryClient, refetchBudgets, refetchCredentials, teamId])

  const isRefreshing = combineFetching(isFetching, budgetsFetching)

  const openEdit = useCallback(
    (c: ProviderCredential): void => {
      onEditCredentialChange?.(c)
    },
    [onEditCredentialChange]
  )

  const deleteMutation = useMutation({
    mutationFn: gatewayApi.deleteMyCredential,
    onSuccess: (_data, credentialId) => {
      invalidateCredentialProbeCache(queryClient, 'user', credentialId)
      invalidate()
      setCredentialPendingDelete(null)
      if (editCredential?.id === credentialId) {
        onEditCredentialChange?.(null)
      }
      toast({ title: '凭据已删除', description: '关联的个人注册模型已一并移除' })
    },
    onError: (e: Error) => {
      setCredentialPendingDelete(null)
      toast({ variant: 'destructive', title: '删除失败', description: e.message })
    },
  })

  const pendingDeleteRef = useRef<ProviderCredential | null>(null)
  pendingDeleteRef.current = credentialPendingDelete

  const handleDeleteDialogOpenChange = useCallback((open: boolean) => {
    if (!open) setCredentialPendingDelete(null)
  }, [])

  const handleDeleteConfirm = useCallback(() => {
    const pending = pendingDeleteRef.current
    if (pending) {
      deleteMutation.mutate(pending.id)
    }
  }, [deleteMutation])

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
  const { isPending: testIsPending, mutate: testMutate } = testMutation

  const toolbar = (
    <div className="flex flex-wrap items-center gap-2 sm:gap-3">
      <Badge variant="secondary" className="font-normal">
        {credentials.length} 个凭据 · {providerCount} 个提供商
      </Badge>
      <div className="ml-auto flex flex-wrap items-center gap-2">
        <GatewayRefreshButton
          isFetching={isRefreshing}
          ariaLabel="刷新个人凭据"
          onRefresh={handleRefresh}
        />
        {writableTeams.length > 0 && credentials.length > 0 ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setImportDialogState({ open: true, preselectedIds: [] })
            }}
          >
            <Upload className="mr-1.5 h-4 w-4" />
            导入到团队
          </Button>
        ) : null}
        {credentials.length > 0 ? (
          <Button
            variant="outline"
            size="sm"
            disabled={testIsPending}
            onClick={() => {
              const active = credentials.find((row) => row.is_active) ?? credentials[0]
              testMutate(active.id)
            }}
          >
            {testIsPending ? '验证中…' : '验证'}
          </Button>
        ) : null}
        {onAddCredential ? (
          <Button
            size="sm"
            onClick={() => {
              onAddCredential()
            }}
          >
            <Plus className="mr-1.5 h-4 w-4" />
            新增
          </Button>
        ) : null}
      </div>
    </div>
  )

  if (!hasAuthSession) {
    return (
      <GatewayCredentialsEmptyState title="请先登录" description="登录后可管理个人 BYOK 凭据。" />
    )
  }

  const userId = currentUser.id

  return (
    <>
      <GatewayCredentialsListShell
        hintSlot="个人 BYOK 凭据，仅本人可见；注册个人模型前需先配置。"
        toolbar={toolbar}
        isLoading={isLoading}
      >
        <PersonalCredentialsList
          credentials={sortedCredentials}
          routeTeamId={teamId}
          deletePending={deleteMutation.isPending}
          onEdit={openEdit}
          onAddModels={onAddModels}
          onDelete={setCredentialPendingDelete}
        />
      </GatewayCredentialsListShell>

      <Dialog
        open={editCredential !== null}
        onOpenChange={(o) => {
          if (!o) onEditCredentialChange?.(null)
        }}
      >
        {editCredential ? (
          <PersonalCredentialEditDialog
            key={editCredential.id}
            cred={editCredential}
            userId={userId}
            personalBudgets={personalBudgets}
            myModels={myModels}
            onClose={() => {
              onEditCredentialChange?.(null)
            }}
            onSaved={() => {
              invalidateCredentialProbeCache(queryClient, 'user', editCredential.id)
              invalidate()
              onEditCredentialChange?.(null)
            }}
          />
        ) : null}
      </Dialog>

      <CredentialDeleteConfirmDialog
        credential={credentialPendingDelete}
        isPending={deleteMutation.isPending}
        variant="personal"
        onOpenChange={handleDeleteDialogOpenChange}
        onConfirm={handleDeleteConfirm}
      />

      <Suspense
        fallback={
          <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            加载导入…
          </div>
        }
      >
        <ImportToTeamDialog
          open={importDialogState.open}
          onOpenChange={(next) => {
            setImportDialogState((prev) => ({ ...prev, open: next }))
          }}
          preselectedCredentialIds={importDialogState.preselectedIds}
          credentials={credentials}
          writableTeams={writableTeams}
        />
      </Suspense>
    </>
  )
}

export function PersonalCredentialEditDialog({
  cred,
  userId,
  personalBudgets,
  myModels,
  onClose,
  onSaved,
}: Readonly<{
  cred: ProviderCredential
  userId: string
  personalBudgets: readonly GatewayBudget[]
  myModels: readonly PersonalGatewayModel[]
  onClose: () => void
  onSaved: () => void
}>): React.ReactElement {
  const { toast } = useToast()
  const form = useCredentialEditForm({ cred, trackIsActive: true })

  const revealFn = useCallback(() => gatewayApi.revealMyCredential(cred.id), [cred.id])

  const updateMutation = useMutation({
    mutationFn: (body: GatewayCredentialUpdateBody) => gatewayApi.updateMyCredential(cred.id, body),
    onSuccess: () => {
      toast({ title: '凭据已更新' })
      onSaved()
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '保存失败', description: e.message })
    },
  })

  const handleSave = (): void => {
    if (!form.canSave) return
    updateMutation.mutate(form.buildUpdateBody())
  }

  return (
    <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
      <DialogHeader>
        <DialogTitle>编辑凭据</DialogTitle>
        <DialogDescription>
          修改账号名称、启用状态或密钥；默认显示掩码，需要时可查看完整明文，或点「更换」输入新密钥后保存。
        </DialogDescription>
      </DialogHeader>
      <div className="grid gap-3 py-2">
        <CredentialEditFields
          cred={cred}
          idPrefix="my-cred"
          form={form}
          showActiveSwitch
          revealFn={revealFn}
        />
        {userId ? (
          <div className="rounded-md border bg-muted/20 p-3">
            <p className="mb-2 text-xs text-muted-foreground">平台预算</p>
            <PersonalCredentialBudgetInline
              credentialId={cred.id}
              userId={userId}
              budgets={[...personalBudgets]}
              myModels={[...myModels]}
            />
          </div>
        ) : null}
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={onClose}>
          取消
        </Button>
        <Button onClick={handleSave} disabled={updateMutation.isPending || !form.canSave}>
          {updateMutation.isPending ? '保存中…' : '保存'}
        </Button>
      </DialogFooter>
    </DialogContent>
  )
}
