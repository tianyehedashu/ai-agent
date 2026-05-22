/**
 * 统一「为凭据添加模型」弹窗：上游探测批量导入 + 团队手动注册。
 */

import { lazy, Suspense, useCallback, useMemo, useState } from 'react'

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { gatewayApi, type CredentialProbeResult, type GatewayModelCreateBody } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { credentialProbeCacheKey } from '@/features/gateway-credentials/credential-probe-cache'
import { CredentialUpstreamModelsPanel } from '@/features/gateway-credentials/credential-upstream-models-panel'
import { providerLabel } from '@/features/gateway-credentials/provider-schemas'
import type { CredentialUpstreamScope } from '@/features/gateway-credentials/types'
import { useGatewayModelMutations } from '@/features/gateway-models/hooks/use-gateway-model-mutations'
import { credentialDetailHref, personalModelsRegisterHref } from '@/features/gateway-models/paths'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { Loader2 } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

const RegisterModelForm = lazy(() =>
  import('@/features/gateway-models/team/register-model-form').then((m) => ({
    default: m.RegisterModelForm,
  }))
)

function RegisterFormFallback(): React.JSX.Element {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />
      加载注册表单…
    </div>
  )
}

export interface AddModelsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  scope: CredentialUpstreamScope
  credentialId: string
  provider: string
  credentialName?: string
  isActive?: boolean
  onboardingHint?: string
  /** 个人凭据禁用时：关闭本弹窗并打开编辑 */
  onEditPersonalCredential?: () => void
}

type TeamTab = 'import' | 'manual'

interface TeamManualRegisterTabProps {
  credentialId: string
  provider: string
  credentialName?: string
  open: boolean
  onCloseDialog: () => void
  onBackToImport: () => void
}

function TeamManualRegisterTab({
  credentialId,
  provider,
  credentialName,
  open,
  onCloseDialog,
  onBackToImport,
}: TeamManualRegisterTabProps): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const { data: credentials } = useQuery({
    queryKey: ['gateway', 'credentials', teamId],
    queryFn: () => gatewayApi.listCredentials(teamId),
    enabled: open,
  })

  const { data: presets } = useQuery({
    queryKey: ['gateway', 'models', 'presets', teamId, provider],
    queryFn: () => gatewayApi.listModelPresets(teamId, { provider }),
    enabled: open,
  })

  const activeCredentials = useMemo(
    () => (credentials ?? []).filter((c) => c.is_active || c.id === credentialId),
    [credentials, credentialId]
  )

  const lockCredential = credentials?.find((c) => c.id === credentialId)

  const { createMutation } = useGatewayModelMutations({
    credentialId,
    onCreateSuccess: onCloseDialog,
  })

  const handleManualSubmit = useCallback(
    (body: GatewayModelCreateBody) => {
      createMutation.mutate(body)
    },
    [createMutation]
  )

  return (
    <Suspense fallback={<RegisterFormFallback />}>
      <RegisterModelForm
        embedded
        presets={presets ?? []}
        credentials={activeCredentials}
        lockCredentialId={credentialId}
        lockCredentialLabel={lockCredential?.name ?? credentialName}
        initialProvider={provider}
        cancelLabel="返回导入"
        onSubmit={handleManualSubmit}
        onCancel={onBackToImport}
        isSubmitting={createMutation.isPending}
      />
    </Suspense>
  )
}

export function AddModelsDialog({
  open,
  onOpenChange,
  scope,
  credentialId,
  provider,
  credentialName,
  isActive = true,
  onboardingHint,
  onEditPersonalCredential,
}: AddModelsDialogProps): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const [teamTab, setTeamTab] = useState<TeamTab>('import')
  const [lastProbe, setLastProbe] = useState<CredentialProbeResult | null>(null)

  const probeCacheKey = useMemo(
    () => credentialProbeCacheKey(scope, credentialId),
    [scope, credentialId]
  )

  const handleDialogOpenChange = useCallback(
    (next: boolean) => {
      if (next) {
        setTeamTab('import')
        setLastProbe(null)
      }
      onOpenChange(next)
    },
    [onOpenChange]
  )

  const handleProbeResult = useCallback(
    (result: CredentialProbeResult) => {
      setLastProbe(result)
      if (result.support === 'unsupported' && scope === 'team') {
        setTeamTab('manual')
      }
    },
    [scope]
  )

  const handleImported = useCallback(
    (count: number) => {
      if (count > 0) onOpenChange(false)
    },
    [onOpenChange]
  )

  const showUnsupportedBanner =
    scope === 'team' && lastProbe?.support === 'unsupported' && teamTab === 'import'

  const titleName = credentialName?.trim() ? credentialName : '凭据'
  const probeWhenActive = open && isActive

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="flex max-h-[90vh] max-w-2xl flex-col gap-0 overflow-hidden p-0">
        <DialogHeader className="shrink-0 space-y-1 border-b px-6 py-4">
          <DialogTitle>为「{titleName}」添加模型</DialogTitle>
          <DialogDescription>
            {providerLabel(provider)}
            <span className="ml-1.5 font-mono text-xs">({provider})</span>
            {onboardingHint ? (
              <span className="mt-2 block text-foreground/80">{onboardingHint}</span>
            ) : null}
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
          {!isActive ? (
            <InactiveCredentialBanner
              teamId={teamId}
              scope={scope}
              credentialId={credentialId}
              onEditPersonalCredential={onEditPersonalCredential}
            />
          ) : scope === 'team' ? (
            <Tabs
              value={teamTab}
              onValueChange={(v) => {
                setTeamTab(v as TeamTab)
              }}
            >
              {showUnsupportedBanner ? (
                <UnsupportedProbeBanner
                  onSwitchManual={() => {
                    setTeamTab('manual')
                  }}
                />
              ) : null}
              <TabsList className="mb-4 grid w-full grid-cols-2">
                <TabsTrigger value="import">从上游一键导入</TabsTrigger>
                <TabsTrigger
                  value="manual"
                  className={cn(lastProbe?.support === 'unsupported' && 'ring-2 ring-primary/40')}
                >
                  手动注册单条
                </TabsTrigger>
              </TabsList>
              <TabsContent value="import" className="mt-0 focus-visible:outline-none">
                {teamTab === 'import' ? (
                  <CredentialUpstreamModelsPanel
                    scope="team"
                    credentialId={credentialId}
                    provider={provider}
                    embedded
                    autoProbe={probeWhenActive}
                    cacheKey={probeCacheKey}
                    onProbeResult={handleProbeResult}
                    onImported={handleImported}
                  />
                ) : null}
              </TabsContent>
              <TabsContent value="manual" className="mt-0 focus-visible:outline-none">
                {teamTab === 'manual' ? (
                  <TeamManualRegisterTab
                    credentialId={credentialId}
                    provider={provider}
                    credentialName={credentialName}
                    open={open}
                    onCloseDialog={() => {
                      onOpenChange(false)
                    }}
                    onBackToImport={() => {
                      setTeamTab('import')
                    }}
                  />
                ) : null}
              </TabsContent>
            </Tabs>
          ) : (
            <div className="space-y-3">
              {lastProbe?.support === 'unsupported' ? (
                <UserUnsupportedHint teamId={teamId} credentialId={credentialId} />
              ) : null}
              <CredentialUpstreamModelsPanel
                scope="user"
                credentialId={credentialId}
                provider={provider}
                embedded
                autoProbe={probeWhenActive}
                cacheKey={probeCacheKey}
                onProbeResult={handleProbeResult}
                onImported={handleImported}
              />
            </div>
          )}
        </div>

        <DialogFooter className="shrink-0 border-t px-6 py-3 sm:justify-between">
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              handleDialogOpenChange(false)
            }}
          >
            稍后再说
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function InactiveCredentialBanner({
  teamId,
  scope,
  credentialId,
  onEditPersonalCredential,
}: {
  teamId: string
  scope: CredentialUpstreamScope
  credentialId: string
  onEditPersonalCredential?: () => void
}): React.JSX.Element {
  return (
    <div
      role="status"
      className="rounded-md border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-900 dark:text-amber-200"
    >
      <p className="font-medium">凭据已禁用</p>
      <p className="mt-1 text-muted-foreground">请先启用凭据后再探测上游或添加模型。</p>
      <div>
        {scope === 'team' ? (
          <Button type="button" variant="link" className="mt-2 h-auto p-0" asChild>
            <Link to={credentialDetailHref(teamId, credentialId)}>前往凭据详情启用</Link>
          </Button>
        ) : onEditPersonalCredential ? (
          <Button
            type="button"
            variant="link"
            className="mt-2 h-auto p-0"
            onClick={onEditPersonalCredential}
          >
            编辑凭据以启用
          </Button>
        ) : null}
      </div>
    </div>
  )
}

function UnsupportedProbeBanner({
  onSwitchManual,
}: {
  onSwitchManual: () => void
}): React.JSX.Element {
  return (
    <div
      role="status"
      className="mb-3 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-sm"
    >
      此提供商不支持自动列举模型。{' '}
      <button
        type="button"
        className="font-medium text-primary underline-offset-4 hover:underline"
        onClick={onSwitchManual}
      >
        改用手动注册 →
      </button>
    </div>
  )
}

function UserUnsupportedHint({
  teamId,
  credentialId,
}: {
  teamId: string
  credentialId: string
}): React.JSX.Element {
  return (
    <div
      role="status"
      className="rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-sm text-amber-900 dark:text-amber-200"
    >
      此提供商不支持自动列举。可在{' '}
      <Link
        to={personalModelsRegisterHref(teamId, credentialId)}
        className="font-medium text-primary underline-offset-4 hover:underline"
      >
        个人模型注册页
      </Link>{' '}
      中手填 model_id。
    </div>
  )
}
