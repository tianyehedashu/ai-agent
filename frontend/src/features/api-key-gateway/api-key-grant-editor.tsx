/**
 * 平台 API Key 的 Gateway 团队授权编辑器
 */

import type React from 'react'

import { Plus, Trash2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  gatewayTeamDisplayLabel,
  useGatewayTeamNameMap,
  useGatewayWritableTeams,
} from '@/features/gateway-teams/use-gateway-teams'
import type { ApiKeyGatewayGrantRequest } from '@/types/api-key'

import { EMPTY_GRANT_POLICY, type GrantPolicyValues } from './gateway-capability-options'
import { GrantPolicyFields } from './grant-policy-fields'

export interface GrantDraft extends ApiKeyGatewayGrantRequest {
  localId: string
}

function toDraft(grant: ApiKeyGatewayGrantRequest, localId: string): GrantDraft {
  return {
    localId,
    team_id: grant.team_id,
    allowed_models: grant.allowed_models ?? [],
    allowed_capabilities: grant.allowed_capabilities ?? [],
    rpm_limit: grant.rpm_limit ?? null,
    tpm_limit: grant.tpm_limit ?? null,
    store_full_messages: grant.store_full_messages ?? false,
    guardrail_enabled: grant.guardrail_enabled ?? false,
  }
}

function policyFromDraft(draft: GrantDraft): GrantPolicyValues {
  return {
    allowed_models: draft.allowed_models ?? [],
    allowed_capabilities: draft.allowed_capabilities ?? [],
    rpm_limit: draft.rpm_limit ?? null,
    tpm_limit: draft.tpm_limit ?? null,
    store_full_messages: draft.store_full_messages ?? false,
    guardrail_enabled: draft.guardrail_enabled ?? false,
  }
}

interface ApiKeyGrantEditorProps {
  grants: GrantDraft[]
  onChange: (grants: GrantDraft[]) => void
  includePersonalDefaultHint?: boolean
}

export function ApiKeyGrantEditor({
  grants,
  onChange,
  includePersonalDefaultHint = true,
}: ApiKeyGrantEditorProps): React.ReactElement {
  const eligibleTeams = useGatewayWritableTeams()
  const teamNameById = useGatewayTeamNameMap()

  const usedTeamIds = new Set(grants.map((g) => g.team_id))

  const addGrant = (): void => {
    const candidate = eligibleTeams.find((t) => !usedTeamIds.has(t.id))
    if (!candidate) return
    onChange([
      ...grants,
      toDraft({ team_id: candidate.id, ...EMPTY_GRANT_POLICY }, crypto.randomUUID()),
    ])
  }

  return (
    <div className="space-y-3 rounded-lg border bg-muted/20 p-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <Label>Gateway 团队授权</Label>
          {includePersonalDefaultHint ? (
            <p className="text-xs text-muted-foreground">
              未配置时勾选 gateway:proxy 将自动授权个人工作区；共享团队需 owner/admin 身份。
            </p>
          ) : null}
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={eligibleTeams.every((t) => usedTeamIds.has(t.id))}
          onClick={addGrant}
        >
          <Plus className="mr-1 h-3 w-3" />
          添加团队
        </Button>
      </div>

      {grants.length === 0 ? (
        <p className="text-sm text-muted-foreground">使用后端默认 personal team 授权。</p>
      ) : (
        grants.map((grant, index) => (
          <div key={grant.localId} className="space-y-3 rounded-md border bg-background p-3">
            <div className="flex items-center justify-between gap-2">
              <div className="flex min-w-0 flex-1 items-center gap-2">
                <Select
                  value={grant.team_id}
                  onValueChange={(teamId) => {
                    const next = grants.map((g) =>
                      g.localId === grant.localId ? { ...g, team_id: teamId } : g
                    )
                    onChange(next)
                  }}
                >
                  <SelectTrigger className="max-w-xs">
                    <SelectValue placeholder="选择团队" />
                  </SelectTrigger>
                  <SelectContent>
                    {eligibleTeams.map((team) => (
                      <SelectItem
                        key={team.id}
                        value={team.id}
                        disabled={
                          team.id !== grant.team_id && grants.some((g) => g.team_id === team.id)
                        }
                      >
                        {gatewayTeamDisplayLabel(team)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Badge variant="outline" className="shrink-0 text-xs">
                  {teamNameById.get(grant.team_id) ?? grant.team_id.slice(0, 8)}
                </Badge>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => {
                  onChange(grants.filter((g) => g.localId !== grant.localId))
                }}
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </div>
            <GrantPolicyFields
              idPrefix={`grant-${String(index)}`}
              values={policyFromDraft(grant)}
              onChange={(policy) => {
                onChange(
                  grants.map((g) =>
                    g.localId === grant.localId
                      ? {
                          ...g,
                          ...policy,
                        }
                      : g
                  )
                )
              }}
            />
          </div>
        ))
      )}
    </div>
  )
}
