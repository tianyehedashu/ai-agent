/**
 * AI Gateway · 凭据（统一列表）
 */

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react'

import { useQuery } from '@tanstack/react-query'

import { gatewayApi, type ProviderCredential } from '@/api/gateway'
import {
  CreateCredentialDialog,
  type CreateCredentialValues,
} from '@/features/gateway-credentials/create-credential-dialog'
import { useCredentialCreateFlow } from '@/features/gateway-credentials/hooks/use-credential-create-flow'
import { useCredentialHighlight } from '@/features/gateway-credentials/hooks/use-credential-highlight'
import { useCredentialsPageParams } from '@/features/gateway-credentials/hooks/use-credentials-page-params'
import { useGatewayCredentialMutations } from '@/features/gateway-credentials/hooks/use-gateway-credential-mutations'
import type { CredentialFormScope } from '@/features/gateway-credentials/provider-schemas'
import type { CredentialUpstreamScope } from '@/features/gateway-credentials/types'
import { UnifiedCredentialsWorkspace } from '@/features/gateway-credentials/unified/unified-credentials-workspace'
import {
  useGatewayContributorCollaborationTeams,
  useGatewayWritableTeams,
} from '@/features/gateway-teams/use-gateway-teams'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { lazyWithReload } from '@/lib/lazy-with-reload'
import { Loader2 } from '@/lib/lucide-icons'

const AddModelsDialog = lazyWithReload(() =>
  import('@/features/gateway-credentials/add-models-dialog').then((m) => ({
    default: m.AddModelsDialog,
  }))
)

export default function GatewayCredentialsPage(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const writableTeams = useGatewayWritableTeams()
  const contributorCollaborationTeams = useGatewayContributorCollaborationTeams()
  const { canContribute, isPlatformAdmin } = useGatewayPermission()
  const { toast } = useToast()
  const [open, setOpen] = useState(false)
  const [pendingProvider, setPendingProvider] = useState<string | undefined>(undefined)
  const [pendingCreateTeamId, setPendingCreateTeamId] = useState<string | undefined>(undefined)
  const [panelAddModelsCred, setPanelAddModelsCred] = useState<ProviderCredential | null>(null)
  const [editPersonalCred, setEditPersonalCred] = useState<ProviderCredential | null>(null)

  const closeCreateUi = useCallback((): void => {
    setOpen(false)
    setPendingProvider(undefined)
    setPendingCreateTeamId(undefined)
  }, [])

  const createFlow = useCredentialCreateFlow({
    routeTeamId: teamId,
    onCloseCreateUi: closeCreateUi,
  })

  const mutations = useGatewayCredentialMutations({
    teamId,
    onManagedCreateSuccess: (cred, targetTeamId) => {
      const scope: CredentialUpstreamScope = cred.scope === 'system' ? 'system' : 'team'
      createFlow.handleManagedCreateSuccess(cred, targetTeamId, scope)
    },
    onUserCreateSuccess: createFlow.handleUserCreateSuccess,
  })

  const { credentialId, view, setView } = useCredentialsPageParams({
    onBeforeTabChange: closeCreateUi,
  })

  useCredentialHighlight(credentialId)

  const { data: myCredentials = [] } = useQuery({
    queryKey: ['gateway', 'my-credentials'],
    queryFn: () => gatewayApi.listMyCredentials(),
    enabled: credentialId.length > 0,
  })

  useEffect(() => {
    if (view === 'create') {
      setOpen(true)
      setView(null)
    }
  }, [view, setView])

  useEffect(() => {
    if (!credentialId || myCredentials.length === 0) return
    const match = myCredentials.find((c) => c.id === credentialId)
    if (match) {
      setEditPersonalCred(match)
    }
  }, [credentialId, myCredentials])

  const allowedScopes = useMemo<ReadonlyArray<CredentialFormScope>>(() => {
    const scopes: CredentialFormScope[] = ['user']
    if (canContribute && contributorCollaborationTeams.length > 0) scopes.push('team')
    if (isPlatformAdmin) scopes.push('system')
    return scopes
  }, [canContribute, contributorCollaborationTeams.length, isPlatformAdmin])

  const createSubmitting =
    mutations.createManagedMutation.isPending || mutations.createUserMutation.isPending

  const handleOpenCreate = useCallback((provider?: string, targetTeamId?: string): void => {
    setPendingProvider(provider)
    setPendingCreateTeamId(targetTeamId)
    setOpen(true)
  }, [])

  const handleDialogOpenChange = useCallback((next: boolean): void => {
    setOpen(next)
    if (!next) {
      setPendingProvider(undefined)
      setPendingCreateTeamId(undefined)
    }
  }, [])

  const onCreateSubmit = useCallback(
    (v: CreateCredentialValues): void => {
      if (v.scope === 'user') {
        mutations.createUserMutation.mutate({
          provider: v.provider,
          name: v.name,
          api_key: v.api_key,
          api_base: v.api_base ?? null,
          api_bases: v.api_bases ?? null,
          profile_id: v.profile_id ?? null,
          extra: v.extra,
        })
        return
      }
      if (v.scope === 'team') {
        if (!v.teamId) {
          toast({
            variant: 'destructive',
            title: '创建失败',
            description: '请选择目标团队',
          })
          return
        }
        mutations.createManagedMutation.mutate({
          targetTeamId: v.teamId,
          body: {
            provider: v.provider,
            name: v.name,
            api_key: v.api_key,
            api_base: v.api_base,
            api_bases: v.api_bases ?? null,
            profile_id: v.profile_id ?? null,
            extra: v.extra,
            scope: v.scope,
          },
        })
        return
      }
      mutations.createManagedMutation.mutate({
        targetTeamId: teamId,
        body: {
          provider: v.provider,
          name: v.name,
          api_key: v.api_key,
          api_base: v.api_base,
          api_bases: v.api_bases ?? null,
          profile_id: v.profile_id ?? null,
          extra: v.extra,
          scope: v.scope,
        },
      })
    },
    [mutations.createManagedMutation, mutations.createUserMutation, teamId, toast]
  )

  const defaultCreateTeamId =
    pendingCreateTeamId ??
    (contributorCollaborationTeams[0] ? contributorCollaborationTeams[0].id : teamId)

  const addModelsTarget = createFlow.justCreated
    ? {
        teamId: createFlow.justCreated.teamId,
        scope: createFlow.justCreated.scope,
        credentialId: createFlow.justCreated.id,
        provider: createFlow.justCreated.provider,
        credentialName: createFlow.justCreated.name,
        isActive: createFlow.justCreated.is_active,
        onboardingHint: '凭据已创建。现在可以快速添加模型，也可以稍后在详情页操作。',
        onClose: () => {
          createFlow.clearJustCreated()
        },
      }
    : panelAddModelsCred
      ? {
          teamId,
          scope: 'user' as const,
          credentialId: panelAddModelsCred.id,
          provider: panelAddModelsCred.provider,
          credentialName: panelAddModelsCred.name,
          isActive: panelAddModelsCred.is_active,
          onboardingHint: undefined,
          onClose: () => {
            setPanelAddModelsCred(null)
          },
          onEditPersonalCredential: () => {
            const target = panelAddModelsCred
            setPanelAddModelsCred(null)
            setEditPersonalCred(target)
          },
        }
      : null

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">凭据</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          管理个人 BYOK、协作团队与系统上游 API Key。
        </p>
      </div>

      <UnifiedCredentialsWorkspace
        mutations={mutations}
        onAdd={handleOpenCreate}
        editPersonalCredential={editPersonalCred}
        onEditPersonalCredentialChange={setEditPersonalCred}
        onAddModelsPersonal={(cred) => {
          setPanelAddModelsCred(cred)
        }}
      />

      <CreateCredentialDialog
        open={open}
        onOpenChange={handleDialogOpenChange}
        allowedScopes={allowedScopes}
        defaultScope="user"
        defaultProvider={pendingProvider}
        writableTeams={
          contributorCollaborationTeams.length > 0 ? contributorCollaborationTeams : writableTeams
        }
        defaultTeamId={defaultCreateTeamId}
        routeTeamId={teamId}
        submitting={createSubmitting}
        onSubmit={onCreateSubmit}
      />

      {addModelsTarget ? (
        <Suspense
          fallback={
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              加载添加模型…
            </div>
          }
        >
          <AddModelsDialog
            open
            onOpenChange={(next: boolean) => {
              if (!next) addModelsTarget.onClose()
            }}
            teamId={addModelsTarget.teamId}
            scope={addModelsTarget.scope}
            credentialId={addModelsTarget.credentialId}
            provider={addModelsTarget.provider}
            credentialName={addModelsTarget.credentialName}
            isActive={addModelsTarget.isActive}
            onboardingHint={addModelsTarget.onboardingHint}
            onEditPersonalCredential={
              'onEditPersonalCredential' in addModelsTarget
                ? addModelsTarget.onEditPersonalCredential
                : undefined
            }
          />
        </Suspense>
      ) : null}
    </div>
  )
}
