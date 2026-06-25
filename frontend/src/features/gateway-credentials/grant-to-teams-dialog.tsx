/**
 * 将个人 BYOK 凭据授权到协作团队（Share-not-Copy，共享同一 credential_id）。
 */

import { useMemo, useState } from 'react'

import type { ProviderCredential } from '@/api/gateway/credentials'
import type { GatewayTeam } from '@/api/gateway/teams'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { useGrantResourceToTeams } from '@/features/gateway-credentials/use-resource-grants'
import { useToast } from '@/hooks/use-toast'
import { Loader2 } from '@/lib/lucide-icons'

import { credentialProviderLabel } from './constants'

export interface GrantCredentialsToTeamsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  credentials: readonly ProviderCredential[]
  contributorTeams: GatewayTeam[]
  teamNameById: Map<string, string>
  preselectedCredentialIds?: string[]
}

export function GrantCredentialsToTeamsDialog({
  open,
  onOpenChange,
  credentials,
  contributorTeams,
  teamNameById,
  preselectedCredentialIds = [],
}: GrantCredentialsToTeamsDialogProps) {
  const { toast } = useToast()
  const grantMutation = useGrantResourceToTeams()
  const personalCreds = useMemo(() => credentials.filter((c) => c.scope === 'user'), [credentials])
  const [selectedCredIds, setSelectedCredIds] = useState<string[]>(preselectedCredentialIds)
  const [selectedTeamIds, setSelectedTeamIds] = useState<string[]>([])

  const toggleCred = (id: string) => {
    setSelectedCredIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const toggleTeam = (id: string) => {
    setSelectedTeamIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const handleSubmit = async () => {
    if (selectedCredIds.length === 0 || selectedTeamIds.length === 0) {
      toast({ title: '请选择凭据与目标团队', variant: 'destructive' })
      return
    }
    try {
      for (const credId of selectedCredIds) {
        await grantMutation.mutateAsync({
          subject_kind: 'credential',
          subject_id: credId,
          target_team_ids: selectedTeamIds,
        })
      }
      toast({ title: '授权成功', description: '团队将共享同一凭据行，上游配额统一生效。' })
      onOpenChange(false)
    } catch (err) {
      toast({
        title: '授权失败',
        description: err instanceof Error ? err.message : '未知错误',
        variant: 'destructive',
      })
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>授权到团队</DialogTitle>
          <DialogDescription>
            共享本人 BYOK 凭据（不复制），多团队共用同一上游配额桶。
          </DialogDescription>
        </DialogHeader>
        <div className="max-h-[50vh] space-y-4 overflow-y-auto">
          <div>
            <Label className="mb-2 block">个人凭据</Label>
            <div className="space-y-2">
              {personalCreds.map((c) => (
                <label key={c.id} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={selectedCredIds.includes(c.id)}
                    onCheckedChange={() => {
                      toggleCred(c.id)
                    }}
                  />
                  <span>
                    {c.name} ({credentialProviderLabel(c.provider)})
                  </span>
                </label>
              ))}
            </div>
          </div>
          <div>
            <Label className="mb-2 block">目标团队</Label>
            <div className="space-y-2">
              {contributorTeams.map((t) => (
                <label key={t.id} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={selectedTeamIds.includes(t.id)}
                    onCheckedChange={() => {
                      toggleTeam(t.id)
                    }}
                  />
                  <span>{teamNameById.get(t.id) ?? t.name}</span>
                </label>
              ))}
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => {
              onOpenChange(false)
            }}
          >
            取消
          </Button>
          <Button onClick={() => void handleSubmit()} disabled={grantMutation.isPending}>
            {grantMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            确认授权
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
