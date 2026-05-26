import { useCallback, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { gatewayApi, type ProviderCredential, type SystemVisibility } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { SystemGrantsPanel } from '@/features/gateway-models/team/system-grants-panel'
import {
  resolveGatewayTeamLabel,
  useGatewayTeamNameMap,
} from '@/features/gateway-teams/use-gateway-teams'
import { useToast } from '@/hooks/use-toast'
import { Loader2, Shield } from '@/lib/lucide-icons'

interface SystemCredentialVisibilityCardProps {
  cred: ProviderCredential
  teamId: string
}

function grantsQueryKey(credentialId: string): string[] {
  return ['gateway', 'system-grants', 'credential', credentialId]
}

export function SystemCredentialVisibilityCard({
  cred,
  teamId,
}: SystemCredentialVisibilityCardProps): React.JSX.Element {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const teamNameById = useGatewayTeamNameMap()
  const [grantsOpen, setGrantsOpen] = useState(false)
  const isRestricted = cred.visibility === 'restricted'

  const { data: grants = [], isLoading: grantsLoading } = useQuery({
    queryKey: grantsQueryKey(cred.id),
    queryFn: () => gatewayApi.listCredentialGrants(cred.id),
    enabled: isRestricted,
  })

  const patchMutation = useMutation({
    mutationFn: (visibility: SystemVisibility) =>
      gatewayApi.patchCredentialVisibility(cred.id, visibility),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'credential', teamId, cred.id] })
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'credentials'] })
      toast({ title: '凭据可见性已更新' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '更新失败', description: e.message })
    },
  })

  const handleToggle = useCallback(
    (checked: boolean) => {
      patchMutation.mutate(checked ? 'restricted' : 'public')
    },
    [patchMutation]
  )

  const enabledTeamGrants = grants.filter((g) => g.target_kind === 'team' && g.enabled)
  const enabledUserGrants = grants.filter((g) => g.target_kind === 'user' && g.enabled)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">可见性与授权</CardTitle>
        <CardDescription>
          受限时，其下继承可见性的系统模型仅对授权团队/用户可见。配额与定价请在预算/定价页配置。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between gap-3 rounded-md border px-3 py-2">
          <div>
            <Label htmlFor="cred-visibility-restricted" className="text-sm font-medium">
              受限访问
            </Label>
            <p className="text-xs text-muted-foreground">
              {isRestricted ? '仅白名单 team/user 可见' : '对所有团队与用户公开'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {patchMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            ) : null}
            <Switch
              id="cred-visibility-restricted"
              checked={isRestricted}
              disabled={patchMutation.isPending}
              onCheckedChange={handleToggle}
            />
          </div>
        </div>
        {isRestricted ? (
          <div className="rounded-md border bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
            {grantsLoading ? (
              <span>加载授权摘要…</span>
            ) : enabledTeamGrants.length === 0 && enabledUserGrants.length === 0 ? (
              <span>暂无有效授权（restricted 时对所有人不可见）</span>
            ) : (
              <div className="space-y-1">
                {enabledTeamGrants.length > 0 ? (
                  <p>
                    已授权团队 ({enabledTeamGrants.length})：
                    {enabledTeamGrants
                      .map((g) => resolveGatewayTeamLabel(teamNameById, g.target_id))
                      .join('、')}
                  </p>
                ) : null}
                {enabledUserGrants.length > 0 ? (
                  <p>已授权用户 ({enabledUserGrants.length})</p>
                ) : null}
              </div>
            )}
          </div>
        ) : null}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => {
            setGrantsOpen(true)
          }}
        >
          <Shield className="mr-1.5 h-4 w-4" />
          管理授权对象
        </Button>
        <SystemGrantsPanel
          open={grantsOpen}
          onOpenChange={setGrantsOpen}
          subjectKind="credential"
          subjectId={cred.id}
          subjectLabel={`${cred.provider} · ${cred.name}`}
        />
      </CardContent>
    </Card>
  )
}
