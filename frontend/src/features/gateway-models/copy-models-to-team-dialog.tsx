/**
 * 模型批量导入到另一团队对话框。
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import type React from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { ProviderCredential } from '@/api/gateway'
import { fetchAllManagedTeamCredentials } from '@/api/gateway/credentials'
import {
  modelsApi,
  type CopyModelsToTeamResponse,
  type ModelCopyCredentialMode,
} from '@/api/gateway/models'
import type { GatewayTeam } from '@/api/gateway/teams'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  buildCopyModelsToTeamBody,
  buildDefaultGroupPlans,
  buildDestinationTeamOptions,
  filterDestinationCredentialsForGroup,
  groupSelectedModelsForCopy,
  isCopyModelsPlanValid,
  type ModelCopyCredentialGroup,
  type ModelCopyGroupPlanState,
} from '@/features/gateway-models/copy-models-to-team-utils'
import type { GatewayModelListItem } from '@/features/gateway-models/list/types'
import { invalidateUnifiedModelsCache } from '@/features/gateway-models/unified/invalidate-unified-models-cache'
import { gatewayTeamDisplayLabel } from '@/features/gateway-teams/gateway-team-display'
import { useToast } from '@/hooks/use-toast'
import { CheckCircle2, Loader2 } from '@/lib/lucide-icons'

export interface CopyModelsToTeamDialogProps {
  onOpenChange: (open: boolean) => void
  selectedItems: readonly GatewayModelListItem[]
  contributorTeams: readonly GatewayTeam[]
  personalTeamId: string | null | undefined
  viewerUserId: string | null | undefined
}

export function CopyModelsToTeamDialog({
  onOpenChange,
  selectedItems,
  contributorTeams,
  personalTeamId,
  viewerUserId,
}: CopyModelsToTeamDialogProps): React.ReactElement {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const groups = useMemo(() => groupSelectedModelsForCopy(selectedItems), [selectedItems])
  const sourceTeamIds = useMemo(
    () => [...new Set(groups.flatMap((group) => group.sourceTeamIds))],
    [groups]
  )

  const destinationTeams = useMemo(
    () => buildDestinationTeamOptions(contributorTeams, sourceTeamIds, personalTeamId),
    [contributorTeams, sourceTeamIds, personalTeamId]
  )

  const [destinationTeamId, setDestinationTeamId] = useState(() => destinationTeams[0]?.id ?? '')
  const [groupPlans, setGroupPlans] = useState<Record<string, ModelCopyGroupPlanState>>({})
  const [result, setResult] = useState<CopyModelsToTeamResponse | null>(null)

  const teamCredentialsQuery = useQuery({
    queryKey: ['managed-team-credentials', 'copy-models-dialog'],
    queryFn: () => fetchAllManagedTeamCredentials(),
    staleTime: 60_000,
  })

  const fullTeamCredentials = useMemo(
    () => (teamCredentialsQuery.data ?? []).filter((c) => c.management_access !== 'metadata'),
    [teamCredentialsQuery.data]
  )

  const destinationTeam = useMemo(
    () => contributorTeams.find((team) => team.id === destinationTeamId),
    [contributorTeams, destinationTeamId]
  )

  useEffect(() => {
    if (!destinationTeamId && destinationTeams[0]?.id) {
      setDestinationTeamId(destinationTeams[0].id)
    }
  }, [destinationTeamId, destinationTeams])

  useEffect(() => {
    if (!destinationTeamId) return
    setGroupPlans(
      buildDefaultGroupPlans(groups, destinationTeamId, fullTeamCredentials, viewerUserId)
    )
  }, [groups, destinationTeamId, fullTeamCredentials, viewerUserId])

  const planValid = useMemo(() => isCopyModelsPlanValid(groups, groupPlans), [groups, groupPlans])

  const copyMutation = useMutation({
    mutationFn: () =>
      modelsApi.copyModelsToTeam(
        buildCopyModelsToTeamBody(selectedItems, destinationTeamId, groupPlans)
      ),
    onSuccess: (data) => {
      setResult(data)
      invalidateUnifiedModelsCache(queryClient)
      const ok = data.succeeded.length
      const fail = data.failed.length
      toast({
        title: fail > 0 ? '部分模型已导入' : '导入成功',
        description:
          fail > 0
            ? `成功 ${String(ok)} 个，失败 ${String(fail)} 个`
            : `已将 ${String(ok)} 个模型导入目标团队`,
      })
    },
    onError: (error: Error) => {
      toast({
        title: '导入失败',
        description: error.message,
        variant: 'destructive',
      })
    },
  })

  const handlePlanModeChange = useCallback(
    (group: ModelCopyCredentialGroup, mode: ModelCopyCredentialMode): void => {
      setGroupPlans((prev) => {
        if (mode === 'copy_credential') {
          return {
            ...prev,
            [group.sourceCredentialId]: {
              mode: 'copy_credential',
              destinationCredentialId: null,
            },
          }
        }
        const matches = filterDestinationCredentialsForGroup(
          fullTeamCredentials,
          group,
          destinationTeamId,
          viewerUserId
        )
        return {
          ...prev,
          [group.sourceCredentialId]: {
            mode: 'existing',
            destinationCredentialId: matches[0]?.id ?? null,
          },
        }
      })
    },
    [fullTeamCredentials, destinationTeamId, viewerUserId]
  )

  const handleDestCredentialChange = useCallback(
    (sourceCredentialId: string, credentialId: string): void => {
      setGroupPlans((prev) => ({
        ...prev,
        [sourceCredentialId]: {
          mode: 'existing',
          destinationCredentialId: credentialId,
        },
      }))
    },
    []
  )

  const destTeamLabel = destinationTeam
    ? gatewayTeamDisplayLabel(destinationTeam)
    : destinationTeamId

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>导入到团队</DialogTitle>
          <DialogDescription>
            将选中的 {selectedItems.length} 个模型复制到另一团队。按源凭据分组配置目标凭据。
          </DialogDescription>
        </DialogHeader>

        {result ? (
          <div className="space-y-3 py-2 text-sm">
            <div className="flex items-center gap-2 text-emerald-600">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span>
                已导入 {result.succeeded.length} 个模型到 {destTeamLabel}
              </span>
            </div>
            {result.failed.length > 0 ? (
              <ul className="max-h-40 space-y-1 overflow-y-auto rounded-md border p-2 text-xs text-muted-foreground">
                {result.failed.map((item) => (
                  <li key={item.model_id}>
                    {item.model_id.slice(0, 8)}… — {item.reason}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : (
          <div className="space-y-4 py-1">
            <div className="space-y-2">
              <Label>目标团队</Label>
              <Select
                value={destinationTeamId}
                onValueChange={setDestinationTeamId}
                disabled={destinationTeams.length === 0}
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择团队" />
                </SelectTrigger>
                <SelectContent>
                  {destinationTeams.map((team) => (
                    <SelectItem key={team.id} value={team.id}>
                      {gatewayTeamDisplayLabel(team)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {groups.map((group) => (
              <CredentialGroupPlanFields
                key={group.sourceCredentialId}
                group={group}
                plan={groupPlans[group.sourceCredentialId]}
                destinationTeamId={destinationTeamId}
                teamCredentials={fullTeamCredentials}
                viewerUserId={viewerUserId}
                onModeChange={handlePlanModeChange}
                onCredentialChange={handleDestCredentialChange}
              />
            ))}
          </div>
        )}

        <DialogFooter>
          {result ? (
            <Button
              type="button"
              onClick={() => {
                onOpenChange(false)
              }}
            >
              关闭
            </Button>
          ) : (
            <>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  onOpenChange(false)
                }}
              >
                取消
              </Button>
              <Button
                type="button"
                disabled={!planValid || copyMutation.isPending || destinationTeams.length === 0}
                onClick={() => {
                  copyMutation.mutate()
                }}
              >
                {copyMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                确认导入
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

interface CredentialGroupPlanFieldsProps {
  group: ModelCopyCredentialGroup
  plan: ModelCopyGroupPlanState | undefined
  destinationTeamId: string
  teamCredentials: readonly ProviderCredential[]
  viewerUserId: string | null | undefined
  onModeChange: (group: ModelCopyCredentialGroup, mode: ModelCopyCredentialMode) => void
  onCredentialChange: (sourceCredentialId: string, credentialId: string) => void
}

function CredentialGroupPlanFields({
  group,
  plan,
  destinationTeamId,
  teamCredentials,
  viewerUserId,
  onModeChange,
  onCredentialChange,
}: CredentialGroupPlanFieldsProps): React.ReactElement {
  const destOptions = useMemo(
    () =>
      filterDestinationCredentialsForGroup(teamCredentials, group, destinationTeamId, viewerUserId),
    [teamCredentials, group, destinationTeamId, viewerUserId]
  )

  const mode = plan?.mode ?? (destOptions.length > 0 ? 'existing' : 'copy_credential')

  return (
    <div className="space-y-2 rounded-md border p-3">
      <div className="text-sm font-medium">
        {group.credentialName}
        <span className="ml-2 text-xs font-normal text-muted-foreground">
          {group.provider} · {group.modelIds.length} 个模型
        </span>
      </div>

      <Select
        value={mode}
        onValueChange={(value) => {
          onModeChange(group, value as ModelCopyCredentialMode)
        }}
      >
        <SelectTrigger className="h-8 text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="existing" disabled={destOptions.length === 0}>
            使用目标团队已有凭据
          </SelectItem>
          <SelectItem value="copy_credential">复制凭据到目标团队</SelectItem>
        </SelectContent>
      </Select>

      {mode === 'existing' && destOptions.length > 0 ? (
        <Select
          value={plan?.destinationCredentialId ?? destOptions[0].id}
          onValueChange={(value) => {
            onCredentialChange(group.sourceCredentialId, value)
          }}
        >
          <SelectTrigger className="h-8 max-w-xs text-xs">
            <SelectValue placeholder="选择凭据" />
          </SelectTrigger>
          <SelectContent>
            {destOptions.map((cred) => (
              <SelectItem key={cred.id} value={cred.id}>
                {cred.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : null}
    </div>
  )
}
