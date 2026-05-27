import { useCallback, useEffect, useState } from 'react'
import type React from 'react'

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, Search } from 'lucide-react'

import { gatewayApi } from '@/api/gateway'
import type { GatewayTeam, InviteCandidateScope } from '@/api/gateway/teams'
import { PaginationControls } from '@/components/pagination-controls'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { addTeamMembersSequentially } from '@/features/gateway-teams/add-team-members-batch'
import { TeamInviteCandidateList } from '@/features/gateway-teams/team-invite-candidate-list'
import {
  inviteCandidateScopeLabel,
  INVITE_CANDIDATE_SCOPE_SETTINGS_KEY,
  parseInviteCandidateScope,
} from '@/features/gateway-teams/team-invite-candidate-scope'
import {
  GATEWAY_MEMBER_TEAMS_QUERY_KEY,
  GATEWAY_TEAMS_QUERY_KEY,
} from '@/features/gateway-teams/use-gateway-teams'
import { useTeamInviteCandidates } from '@/features/gateway-teams/use-team-invite-candidates'
import { useToast } from '@/hooks/use-toast'
import { TeamRole } from '@/types/permissions'

export interface AddTeamMembersSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  teamId: string
  team: GatewayTeam | undefined
  teamRole: string | null | undefined
  onMembersAdded: () => void
}

function candidateLabel(email: string, name: string | null): string {
  const trimmed = name?.trim()
  return trimmed && trimmed.length > 0 ? trimmed : email
}

export function AddTeamMembersSheet({
  open,
  onOpenChange,
  teamId,
  team,
  teamRole,
  onMembersAdded,
}: AddTeamMembersSheetProps): React.JSX.Element {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const isOwner = teamRole === TeamRole.OWNER

  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [role, setRole] = useState('member')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())
  const [selectedLabels, setSelectedLabels] = useState<Map<string, string>>(() => new Map())
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [directUserId, setDirectUserId] = useState('')

  const inviteScope = parseInviteCandidateScope(team?.settings ?? null)

  const { data, isLoading, isFetching } = useTeamInviteCandidates({
    teamId,
    search,
    page,
    enabled: open && teamId.length > 0,
  })

  const resetForm = useCallback((): void => {
    setSearch('')
    setPage(1)
    setRole('member')
    setSelectedIds(new Set())
    setSelectedLabels(new Map())
    setProgress(null)
    setDirectUserId('')
    setShowAdvanced(false)
  }, [])

  useEffect(() => {
    if (!open) {
      resetForm()
    }
  }, [open, teamId, resetForm])

  const handleSearchChange = useCallback((value: string): void => {
    setSearch(value)
    setPage(1)
  }, [])

  const handleSelectChange = useCallback(
    (userId: string, checked: boolean, label?: string): void => {
      setSelectedIds((prev) => {
        const next = new Set(prev)
        if (checked) {
          next.add(userId)
        } else {
          next.delete(userId)
        }
        return next
      })
      if (label !== undefined) {
        setSelectedLabels((prev) => {
          const next = new Map(prev)
          if (checked) {
            next.set(userId, label)
          } else {
            next.delete(userId)
          }
          return next
        })
      }
    },
    []
  )

  const handleSelectAllPage = useCallback(
    (checked: boolean): void => {
      const items = data?.items ?? []
      setSelectedIds((prev) => {
        const next = new Set(prev)
        for (const item of items) {
          if (checked) {
            next.add(item.id)
          } else {
            next.delete(item.id)
          }
        }
        return next
      })
      setSelectedLabels((prev) => {
        const next = new Map(prev)
        for (const item of items) {
          const label = candidateLabel(item.email, item.name)
          if (checked) {
            next.set(item.id, label)
          } else {
            next.delete(item.id)
          }
        }
        return next
      })
    },
    [data?.items]
  )

  const updateScopeMutation = useMutation({
    mutationFn: (scope: InviteCandidateScope) => {
      const baseSettings = { ...(team?.settings ?? {}) }
      return gatewayApi.updateTeam(teamId, {
        settings: { ...baseSettings, [INVITE_CANDIDATE_SCOPE_SETTINGS_KEY]: scope },
      })
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: GATEWAY_TEAMS_QUERY_KEY })
      void queryClient.invalidateQueries({ queryKey: GATEWAY_MEMBER_TEAMS_QUERY_KEY })
      void queryClient.invalidateQueries({
        queryKey: ['gateway', 'teams', teamId, 'invite-candidates'],
      })
      toast({ title: '可发现范围已更新' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '更新失败', description: e.message })
    },
  })

  const handleSubmit = async (): Promise<void> => {
    const directId = directUserId.trim()
    const ids = selectedIds.size > 0 ? Array.from(selectedIds) : directId ? [directId] : []

    if (ids.length === 0) {
      toast({ variant: 'destructive', title: '请勾选用户或输入用户 ID' })
      return
    }

    const items = ids.map((userId) => ({
      userId,
      label: selectedLabels.get(userId) ?? userId,
    }))

    setIsSubmitting(true)
    setProgress({ done: 0, total: items.length })
    try {
      const result = await addTeamMembersSequentially(teamId, items, role, (done, total) => {
        setProgress({ done, total })
      })
      onMembersAdded()
      if (result.failures.length === 0) {
        toast({ title: `已添加 ${String(result.succeeded)} 人` })
        onOpenChange(false)
      } else if (result.succeeded > 0) {
        toast({
          variant: 'destructive',
          title: `已添加 ${String(result.succeeded)} 人，${String(result.failures.length)} 人失败`,
          description: result.failures.map((f) => `${f.label}: ${f.message}`).join('；'),
        })
        onOpenChange(false)
      } else {
        toast({
          variant: 'destructive',
          title: '添加失败',
          description: result.failures.map((f) => `${f.label}: ${f.message}`).join('；'),
        })
      }
    } finally {
      setIsSubmitting(false)
      setProgress(null)
    }
  }

  const selectedCount = selectedIds.size
  const listDisabled = isSubmitting || updateScopeMutation.isPending

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="flex w-full flex-col sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>添加成员</SheetTitle>
          <SheetDescription className="text-left">
            搜索邮箱或姓名，勾选用户后批量加入团队。当前可发现范围：
            {inviteCandidateScopeLabel(inviteScope)}。
          </SheetDescription>
        </SheetHeader>

        <div className="flex min-h-0 flex-1 flex-col gap-3 py-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => {
                handleSearchChange(e.target.value)
              }}
              placeholder="搜索邮箱或姓名"
              className="pl-8"
              disabled={listDisabled}
              aria-label="搜索可邀请用户"
            />
          </div>

          {isOwner ? (
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">可发现范围（仅所有者）</Label>
              <Select
                value={inviteScope}
                disabled={listDisabled}
                onValueChange={(value) => {
                  updateScopeMutation.mutate(value as InviteCandidateScope)
                }}
              >
                <SelectTrigger className="h-8 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all_users">全站注册用户</SelectItem>
                  <SelectItem value="shared_teams">仅共同团队网络</SelectItem>
                </SelectContent>
              </Select>
            </div>
          ) : null}

          {data && data.total > 0 ? (
            <Badge variant="secondary" className="w-fit font-normal">
              共 {data.total} 人可添加
            </Badge>
          ) : null}

          <TeamInviteCandidateList
            items={data?.items ?? []}
            selectedIds={selectedIds}
            isLoading={isLoading}
            submitDisabled={listDisabled}
            onSelectChange={(userId, checked) => {
              const item = data?.items.find((i) => i.id === userId)
              const label = item
                ? candidateLabel(item.email, item.name)
                : (selectedLabels.get(userId) ?? userId)
              handleSelectChange(userId, checked, label)
            }}
            onSelectAllPage={handleSelectAllPage}
          />

          {data && data.total > 0 ? (
            <PaginationControls
              page={data.page}
              page_size={data.page_size}
              total={data.total}
              has_next={data.has_next}
              has_prev={data.has_prev}
              onPageChange={setPage}
            />
          ) : null}

          {isFetching && !isLoading ? (
            <p className="text-center text-xs text-muted-foreground">刷新列表…</p>
          ) : null}

          <div className="space-y-1.5">
            <Label>加入角色</Label>
            <Select value={role} onValueChange={setRole} disabled={listDisabled}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="member">成员</SelectItem>
                <SelectItem value="admin">管理员</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
            <CollapsibleTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 px-0 text-xs text-muted-foreground"
              >
                高级：直接输入用户 ID
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="pt-2">
              <Label>用户 ID</Label>
              <Input
                value={directUserId}
                onChange={(e) => {
                  setDirectUserId(e.target.value)
                }}
                placeholder="UUID"
                disabled={listDisabled || selectedCount > 0}
              />
            </CollapsibleContent>
          </Collapsible>
        </div>

        <SheetFooter className="flex-row items-center justify-between gap-2 sm:justify-between">
          <span className="text-sm text-muted-foreground">
            {selectedCount > 0 ? `已选 ${String(selectedCount)} 人` : null}
            {progress ? (
              <span className="ml-2 tabular-nums">
                正在添加 {String(progress.done)}/{String(progress.total)}…
              </span>
            ) : null}
          </span>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={isSubmitting}
              onClick={() => {
                onOpenChange(false)
              }}
            >
              取消
            </Button>
            <Button
              type="button"
              disabled={listDisabled || (selectedCount === 0 && !directUserId.trim())}
              onClick={() => void handleSubmit()}
            >
              {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {selectedCount > 0 ? `添加 ${String(selectedCount)} 人` : '添加'}
            </Button>
          </div>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
