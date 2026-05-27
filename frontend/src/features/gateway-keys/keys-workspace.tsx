/**
 * AI Gateway · 虚拟 Key 管理工作区
 */

import { useCallback, useMemo, useState } from 'react'

import { useMutation, useQuery, useQueryClient, useIsFetching } from '@tanstack/react-query'

import { gatewayApi, type VirtualKey } from '@/api/gateway'
import { ConfirmAlertDialog } from '@/components/confirm-alert-dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { useGatewayBudgets } from '@/features/gateway-budget/use-gateway-budgets'
import { CreateKeyDialog, type CreateKeyValues } from '@/features/gateway-keys/create-key-dialog'
import { KeysWorkspaceTable } from '@/features/gateway-keys/keys-workspace-table'
import { useKeysEntitlementsMap } from '@/features/gateway-keys/use-keys-entitlements'
import {
  VirtualKeyRevealDialog,
  type VirtualKeyRevealTarget,
} from '@/features/gateway-keys/virtual-key-reveal-dialog'
import { combineFetching } from '@/features/gateway-shared/combine-fetching'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { gatewayTeamDisplayLabel } from '@/features/gateway-teams/gateway-team-display'
import {
  useGatewayMemberTeamNameMap,
  useGatewayMemberTeams,
} from '@/features/gateway-teams/use-gateway-teams'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useToast } from '@/hooks/use-toast'
import { Plus, Trash2 } from '@/lib/lucide-icons'
import { useUserStore } from '@/stores/user'

export interface GatewayKeysWorkspaceProps {
  teamId: string
}

export function GatewayKeysWorkspace({
  teamId,
}: Readonly<GatewayKeysWorkspaceProps>): React.JSX.Element {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const { isMember, isPlatformViewer } = useGatewayPermission()
  const canManageKeys = isMember && !isPlatformViewer
  const viewerUserId = useUserStore((s) => s.currentUser?.id ?? null)
  const keysQueryKey = useMemo(() => ['gateway', 'keys', teamId] as const, [teamId])
  const { data: memberTeams = [] } = useGatewayMemberTeams()
  const teamNameById = useGatewayMemberTeamNameMap()
  const currentTeam = memberTeams.find((t) => t.id === teamId)
  const teamDisplayName = currentTeam
    ? gatewayTeamDisplayLabel(currentTeam, { viewerUserId })
    : `${teamId.slice(0, 8)}…`

  const [open, setOpen] = useState(false)
  const [createdKey, setCreatedKey] = useState<string | null>(null)
  const [createdKeyId, setCreatedKeyId] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [batchRevokeOpen, setBatchRevokeOpen] = useState(false)
  const [revokeOpen, setRevokeOpen] = useState(false)
  const [pendingRevoke, setPendingRevoke] = useState<{ id: string; name: string } | null>(null)
  const [revealTarget, setRevealTarget] = useState<VirtualKeyRevealTarget | null>(null)

  const modelsHref = `/gateway/teams/${encodeURIComponent(teamId)}/models`

  const {
    data: keys,
    isLoading,
    isFetching,
    refetch: refetchKeys,
  } = useQuery({
    queryKey: keysQueryKey,
    queryFn: () => gatewayApi.listKeys(teamId),
  })
  const {
    data: keyBudgets = [],
    isFetching: budgetsFetching,
    refetch: refetchBudgets,
  } = useGatewayBudgets(teamId)
  const budgetsByKeyId = useMemo(() => {
    const map = new Map<string, typeof keyBudgets>()
    for (const b of keyBudgets) {
      if (b.target_kind !== 'key' || b.target_id === null) continue
      const list = map.get(b.target_id) ?? []
      list.push(b)
      map.set(b.target_id, list)
    }
    return map
  }, [keyBudgets])

  const visibleKeys = useMemo(() => (keys ?? []).filter((k) => !k.is_system && k.is_active), [keys])
  const visibleVkeyIds = useMemo(() => visibleKeys.map((k) => k.id), [visibleKeys])
  const entitlementsFetching =
    useIsFetching({
      queryKey: ['gateway', 'keys', teamId],
      predicate: (query) => query.queryKey.length === 5 && query.queryKey[4] === 'entitlements',
    }) > 0
  const { activeByVkeyId, isLoadingByVkeyId } = useKeysEntitlementsMap(teamId, visibleVkeyIds)

  const showEntitlementsColumn = useMemo(
    () => visibleKeys.some((k) => (activeByVkeyId.get(k.id) ?? []).length > 0),
    [visibleKeys, activeByVkeyId]
  )
  const showBudgetsColumn = useMemo(
    () => visibleKeys.some((k) => (budgetsByKeyId.get(k.id) ?? []).length > 0),
    [visibleKeys, budgetsByKeyId]
  )

  const columnCount =
    (canManageKeys ? 1 : 0) + 6 + (showEntitlementsColumn ? 1 : 0) + (showBudgetsColumn ? 1 : 0) + 1

  const allSelectableSelected =
    visibleKeys.length > 0 && visibleKeys.every((k) => selectedIds.has(k.id))
  const someSelectableSelected = visibleKeys.some((k) => selectedIds.has(k.id))

  const { mutate: createKey } = useMutation({
    mutationFn: (body: CreateKeyValues) => gatewayApi.createKey(teamId, body),
    onSuccess: (created) => {
      setCreatedKey(created.plain_key)
      setCreatedKeyId(created.id)
      void queryClient.invalidateQueries({ queryKey: keysQueryKey })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '创建失败', description: e.message })
    },
  })

  const revokeMutation = useMutation({
    mutationFn: (id: string) => gatewayApi.revokeKey(teamId, id),
    onSuccess: (_result, id) => {
      queryClient.setQueryData<VirtualKey[]>(keysQueryKey, (prev) =>
        (prev ?? []).filter((k) => k.id !== id)
      )
      setSelectedIds((prev) => {
        if (!prev.has(id)) return prev
        const next = new Set(prev)
        next.delete(id)
        return next
      })
      void queryClient.invalidateQueries({ queryKey: keysQueryKey })
      toast({ title: '已撤销' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '撤销失败', description: e.message })
    },
  })

  const batchRevokeMutation = useMutation({
    mutationFn: (ids: string[]) => gatewayApi.revokeKeysBatch(teamId, ids),
    onSuccess: (result) => {
      const revokedSet = new Set(result.revoked)
      queryClient.setQueryData<VirtualKey[]>(keysQueryKey, (prev) =>
        (prev ?? []).filter((k) => !revokedSet.has(k.id))
      )
      setSelectedIds(new Set(result.failed.map((item) => item.key_id)))
      void queryClient.invalidateQueries({ queryKey: keysQueryKey })
      setBatchRevokeOpen(false)
      if (result.failed.length === 0) {
        toast({ title: `已撤销 ${String(result.revoked.length)} 个虚拟 Key` })
        return
      }
      toast({
        variant: 'destructive',
        title: '部分撤销失败',
        description: `成功 ${String(result.revoked.length)} 个，失败 ${String(result.failed.length)} 个`,
      })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '批量撤销失败', description: e.message })
    },
  })

  const toggleSelectAll = useCallback(
    (checked: boolean): void => {
      if (checked) {
        setSelectedIds(new Set(visibleKeys.map((k) => k.id)))
        return
      }
      setSelectedIds(new Set())
    },
    [visibleKeys]
  )

  const toggleSelect = useCallback((id: string, checked: boolean): void => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }, [])

  const handleCreateClick = useCallback((): void => {
    setOpen(true)
  }, [])

  const handleRevokeRequest = useCallback((id: string, name: string): void => {
    setPendingRevoke({ id, name })
    setRevokeOpen(true)
  }, [])

  const handleCreateDialogOpenChange = useCallback((v: boolean): void => {
    setOpen(v)
    if (!v) {
      setCreatedKey(null)
      setCreatedKeyId(null)
    }
  }, [])

  const handleCreateSubmit = useCallback(
    (values: CreateKeyValues): void => {
      createKey(values)
    },
    [createKey]
  )

  const handleCloseReveal = useCallback((): void => {
    setRevealTarget(null)
  }, [])

  const handleRefresh = useCallback((): void => {
    void Promise.all([
      refetchKeys(),
      refetchBudgets(),
      queryClient.invalidateQueries({
        queryKey: ['gateway', 'keys', teamId],
        predicate: (query) => query.queryKey.length === 5 && query.queryKey[4] === 'entitlements',
      }),
    ])
  }, [queryClient, refetchBudgets, refetchKeys, teamId])

  const isRefreshing = combineFetching(isFetching, budgetsFetching, entitlementsFetching)

  const createButton = canManageKeys ? (
    <Button size="sm" onClick={handleCreateClick}>
      <Plus className="mr-1.5 h-4 w-4" />
      新建虚拟 Key
    </Button>
  ) : (
    <Tooltip>
      <TooltipTrigger asChild>
        <span>
          <Button size="sm" disabled>
            <Plus className="mr-1.5 h-4 w-4" />
            新建虚拟 Key
          </Button>
        </span>
      </TooltipTrigger>
      <TooltipContent>需团队成员权限</TooltipContent>
    </Tooltip>
  )

  return (
    <TooltipProvider>
      <div className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-2xl font-semibold tracking-tight">虚拟 Key</h2>
              <Badge
                variant="secondary"
                className="max-w-[12rem] truncate font-normal"
                title={teamId}
              >
                {teamDisplayName}
              </Badge>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <GatewayRefreshButton
              isFetching={isRefreshing}
              ariaLabel="刷新虚拟 Key"
              onRefresh={handleRefresh}
            />
            {createButton}
          </div>
        </div>

        {canManageKeys && selectedIds.size > 0 ? (
          <div className="flex items-center justify-between rounded-md border bg-muted/30 px-4 py-2">
            <span className="text-sm text-muted-foreground">已选 {selectedIds.size} 项</span>
            <Button
              size="sm"
              variant="destructive"
              onClick={() => {
                setBatchRevokeOpen(true)
              }}
            >
              <Trash2 className="mr-1.5 h-4 w-4" />
              批量撤销
            </Button>
          </div>
        ) : null}

        <KeysWorkspaceTable
          teamDisplayName={teamDisplayName}
          teamNameById={teamNameById}
          modelsHref={modelsHref}
          canManageKeys={canManageKeys}
          isLoading={isLoading}
          isFetching={isFetching}
          visibleKeys={visibleKeys}
          showEntitlementsColumn={showEntitlementsColumn}
          showBudgetsColumn={showBudgetsColumn}
          columnCount={columnCount}
          allSelectableSelected={allSelectableSelected}
          someSelectableSelected={someSelectableSelected}
          selectedIds={selectedIds}
          activeByVkeyId={activeByVkeyId}
          isLoadingByVkeyId={isLoadingByVkeyId}
          budgetsByKeyId={budgetsByKeyId}
          onToggleSelectAll={toggleSelectAll}
          onToggleSelect={toggleSelect}
          onReveal={setRevealTarget}
          onRevoke={handleRevokeRequest}
          onCreateClick={handleCreateClick}
        />

        <CreateKeyDialog
          open={open}
          teamId={teamId}
          teamDisplayName={teamDisplayName}
          onOpenChange={handleCreateDialogOpenChange}
          createdKeyId={createdKeyId}
          onSubmit={handleCreateSubmit}
          plaintext={createdKey}
        />

        <VirtualKeyRevealDialog
          teamId={teamId}
          teamDisplayName={teamDisplayName}
          target={revealTarget}
          onClose={handleCloseReveal}
        />

        <ConfirmAlertDialog
          open={revokeOpen}
          onOpenChange={(open) => {
            setRevokeOpen(open)
            if (!open) setPendingRevoke(null)
          }}
          title="撤销虚拟 Key"
          description={
            pendingRevoke
              ? `确定撤销「${pendingRevoke.name}」？撤销后该 Key 将无法继续调用。`
              : '确定撤销该虚拟 Key？'
          }
          confirmLabel="确认撤销"
          pending={revokeMutation.isPending}
          onConfirm={() => {
            if (!pendingRevoke) return
            const id = pendingRevoke.id
            setRevokeOpen(false)
            setPendingRevoke(null)
            revokeMutation.mutate(id)
          }}
        />

        <AlertDialog open={batchRevokeOpen} onOpenChange={setBatchRevokeOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>批量撤销虚拟 Key</AlertDialogTitle>
              <AlertDialogDescription>
                确定撤销已选的 {selectedIds.size} 个虚拟 Key？撤销后对应 Key 将无法继续调用。
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={batchRevokeMutation.isPending}>取消</AlertDialogCancel>
              <AlertDialogAction
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                disabled={batchRevokeMutation.isPending || selectedIds.size === 0}
                onClick={() => {
                  batchRevokeMutation.mutate([...selectedIds])
                }}
              >
                {batchRevokeMutation.isPending ? '撤销中…' : '确认撤销'}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </TooltipProvider>
  )
}
