/**
 * AI Gateway · 凭据（个人 / 团队 / 系统）
 */

import { Suspense, startTransition, useCallback, useMemo, useState } from 'react'
import type React from 'react'

import { Link } from 'react-router-dom'

import { Tabs, TabsContent, TabsList } from '@/components/ui/tabs'
import {
  CreateCredentialDialog,
  type CreateCredentialValues,
} from '@/features/gateway-credentials/create-credential-dialog'
import { useCredentialCreateFlow } from '@/features/gateway-credentials/hooks/use-credential-create-flow'
import { useGatewayCredentialMutations } from '@/features/gateway-credentials/hooks/use-gateway-credential-mutations'
import { PersonalCredentialsPanel } from '@/features/gateway-credentials/personal-credentials-panel'
import type { CredentialFormScope } from '@/features/gateway-credentials/provider-schemas'
import { SystemCredentialsAdminWorkspace } from '@/features/gateway-credentials/system/system-credentials-admin-workspace'
import { TeamCredentialsWorkspace } from '@/features/gateway-credentials/team/team-credentials-workspace'
import type { CredentialUpstreamScope } from '@/features/gateway-credentials/types'
import { isGatewayScopeTabValue } from '@/features/gateway-models/constants'
import { GatewayScopeTabTriggers } from '@/features/gateway-models/gateway-scope-tabs'
import {
  credentialsSystemBrowseIndexHref,
  systemModelsBrowseIndexHref,
} from '@/features/gateway-models/paths'
import {
  useGatewayContributorCollaborationTeams,
  useGatewayWritableTeams,
} from '@/features/gateway-teams/use-gateway-teams'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayScopeTab } from '@/hooks/use-gateway-scope-tab'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { lazyWithReload } from '@/lib/lazy-with-reload'
import { Loader2 } from '@/lib/lucide-icons'

const AddModelsDialog = lazyWithReload(() =>
  import('@/features/gateway-credentials/add-models-dialog').then((m) => ({
    default: m.AddModelsDialog,
  }))
)

const SystemCredentialsBrowseWorkspace = lazyWithReload(() =>
  import('@/features/gateway-credentials/system/system-credentials-browse-workspace').then((m) => ({
    default: m.SystemCredentialsBrowseWorkspace,
  }))
)

function CredentialsPanelFallback(): React.JSX.Element {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />
      加载中…
    </div>
  )
}

export default function GatewayCredentialsPage(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const writableTeams = useGatewayWritableTeams()
  // 团队 Tab：成员（含非管理员）即可为所在协作团队创建创建者私有凭据。
  const contributorCollaborationTeams = useGatewayContributorCollaborationTeams()
  const { canContribute, isPlatformAdmin, isAdmin } = useGatewayPermission()
  const { toast } = useToast()
  const [open, setOpen] = useState(false)
  const [pendingProvider, setPendingProvider] = useState<string | undefined>(undefined)
  const [pendingCreateTeamId, setPendingCreateTeamId] = useState<string | undefined>(undefined)

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

  const { scopeTab: activeTab, setScopeTab: setActiveTab } = useGatewayScopeTab({
    allowSystemTab: true,
    onBeforeTabChange: closeCreateUi,
  })

  const allowedScopes = useMemo<ReadonlyArray<CredentialFormScope>>(() => {
    if (activeTab === 'system' && isPlatformAdmin) return ['system']
    if (activeTab === 'personal') return ['user']
    const scopes: CredentialFormScope[] = ['user']
    // 成员可在所在协作团队下创建团队凭据（创建者私有）。
    if (canContribute && contributorCollaborationTeams.length > 0) scopes.push('team')
    return scopes
  }, [activeTab, canContribute, contributorCollaborationTeams.length, isPlatformAdmin])

  const defaultScope: CredentialFormScope =
    activeTab === 'personal' ? 'user' : activeTab === 'system' ? 'system' : 'team'
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

  const defaultCreateTeamId = useMemo(() => {
    if (pendingCreateTeamId) return pendingCreateTeamId
    if (activeTab === 'shared') {
      return contributorCollaborationTeams[0]?.id ?? undefined
    }
    return teamId
  }, [activeTab, pendingCreateTeamId, teamId, contributorCollaborationTeams])

  const createWritableTeams = activeTab === 'shared' ? contributorCollaborationTeams : writableTeams

  const sharedTabDescription = useMemo(() => {
    if (isAdmin) {
      return '展示您可管理的全部协作团队及其共享凭据；可为任一团队添加上游 API Key。'
    }
    if (contributorCollaborationTeams.length > 0) {
      return '展示您已加入的协作团队凭据；您可为团队添加自己的凭据并管理（仅创建者可改/删），他人凭据密钥已脱敏。'
    }
    return '展示您已加入的协作团队共享凭据（只读）；密钥已脱敏。'
  }, [isAdmin, contributorCollaborationTeams.length])

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">凭据</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {activeTab === 'system' ? (
            isPlatformAdmin ? (
              <>
                系统凭据默认全平台公开；受限后仅授权 team/user 可见（详情 →
                可见性与授权）。挂载模型见{' '}
                <Link
                  to={systemModelsBrowseIndexHref(teamId)}
                  className="text-primary underline-offset-4 hover:underline"
                >
                  系统模型
                </Link>
                。配置同步项在重启或重载后可能自动恢复。
              </>
            ) : (
              <>
                仅显示当前团队有权使用的系统凭据（不含密钥）。挂载模型见{' '}
                <Link
                  to={systemModelsBrowseIndexHref(teamId)}
                  className="text-primary underline-offset-4 hover:underline"
                >
                  系统模型
                </Link>
                ；团队自管凭据见「团队」Tab。
              </>
            )
          ) : activeTab === 'shared' ? (
            <>
              {sharedTabDescription} 系统预置凭据见{' '}
              <Link
                to={credentialsSystemBrowseIndexHref(teamId)}
                className="text-primary underline-offset-4 hover:underline"
              >
                系统
              </Link>{' '}
              Tab。
            </>
          ) : (
            <>个人 BYOK 凭据，仅本人可见；注册个人模型前需先配置。</>
          )}
        </p>
      </div>

      <Tabs
        value={activeTab}
        onValueChange={(v) => {
          if (isGatewayScopeTabValue(v, { allowSystem: true })) {
            startTransition(() => {
              setActiveTab(v)
            })
          }
        }}
      >
        <TabsList>
          <GatewayScopeTabTriggers showSystemTab />
        </TabsList>

        {activeTab === 'personal' ? (
          <TabsContent value="personal" className="mt-4 focus-visible:outline-none">
            <PersonalCredentialsPanel
              onAddCredential={handleOpenCreate}
              writableTeams={writableTeams}
            />
          </TabsContent>
        ) : activeTab === 'system' ? (
          isPlatformAdmin ? (
            <SystemCredentialsAdminWorkspace mutations={mutations} onAdd={handleOpenCreate} />
          ) : (
            <TabsContent value="system" className="mt-4 focus-visible:outline-none">
              <Suspense fallback={<CredentialsPanelFallback />}>
                <SystemCredentialsBrowseWorkspace />
              </Suspense>
            </TabsContent>
          )
        ) : (
          <TeamCredentialsWorkspace mutations={mutations} onAdd={handleOpenCreate} />
        )}
      </Tabs>

      <CreateCredentialDialog
        open={open}
        onOpenChange={handleDialogOpenChange}
        allowedScopes={allowedScopes}
        defaultScope={defaultScope}
        defaultProvider={pendingProvider}
        writableTeams={createWritableTeams}
        defaultTeamId={defaultCreateTeamId}
        routeTeamId={teamId}
        submitting={createSubmitting}
        onSubmit={onCreateSubmit}
      />

      {createFlow.justCreated ? (
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
              if (!next) createFlow.clearJustCreated()
            }}
            teamId={createFlow.justCreated.teamId}
            scope={createFlow.justCreated.scope}
            credentialId={createFlow.justCreated.id}
            provider={createFlow.justCreated.provider}
            credentialName={createFlow.justCreated.name}
            isActive={createFlow.justCreated.is_active}
            onboardingHint="凭据已创建。现在可以快速添加模型，也可以稍后在详情页操作。"
          />
        </Suspense>
      ) : null}
    </div>
  )
}
