/**
 * AI Gateway · 模型（个人 / 团队 / 系统）
 */

import { Suspense, startTransition, useCallback, useEffect } from 'react'

import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList } from '@/components/ui/tabs'
import {
  type GatewayScopeTab,
  isGatewayScopeTabValue,
  parseModelsPageView,
} from '@/features/gateway-models/constants'
import { GatewayScopeTabTriggers } from '@/features/gateway-models/gateway-scope-tabs'
import {
  credentialsSystemBrowseIndexHref,
  personalModelsIndexHref,
  systemModelsBrowseIndexHref,
  systemModelsFilteredHref,
  teamModelsFilteredHref,
} from '@/features/gateway-models/paths'
import { preloadPersonalModelsWorkspace } from '@/features/gateway-models/personal/personal-model-preload'
import { preloadTeamModelsWorkspace } from '@/features/gateway-models/team/preloads'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayScopeTab } from '@/hooks/use-gateway-scope-tab'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { lazyWithReload } from '@/lib/lazy-with-reload'
import { ChevronLeft, Loader2 } from '@/lib/lucide-icons'

const PersonalModelsWorkspace = lazyWithReload(() =>
  import('@/features/gateway-models/personal/personal-models-workspace').then((m) => ({
    default: m.PersonalModelsWorkspace,
  }))
)

const TeamModelsWorkspace = lazyWithReload(() =>
  import('@/features/gateway-models/team/team-models-workspace').then((m) => ({
    default: m.TeamModelsWorkspace,
  }))
)

const SystemModelsBrowseWorkspace = lazyWithReload(() =>
  import('@/features/gateway-models/system/system-models-browse-workspace').then((m) => ({
    default: m.SystemModelsBrowseWorkspace,
  }))
)

function ModelsPanelFallback(): React.JSX.Element {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />
      加载中…
    </div>
  )
}

export default function GatewayModelsPage(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const { canWrite, isPlatformAdmin } = useGatewayPermission()
  const mutateParamsOnTabChange = useCallback(
    (next: GatewayScopeTab, params: URLSearchParams) => {
      params.delete('view')
      if (next === 'personal') {
        params.delete('credentialId')
        params.delete('modelId')
      }
      if (next === 'system' && !isPlatformAdmin) {
        params.delete('credentialId')
        params.delete('modelId')
      }
    },
    [isPlatformAdmin]
  )
  const { scopeTab, setScopeTab, searchParams, setSearchParams } = useGatewayScopeTab({
    allowSystemTab: true,
    mutateParamsOnTabChange,
  })
  const pageView = parseModelsPageView(searchParams.get('view'))
  const credentialId = searchParams.get('credentialId') ?? ''
  const isTeamRegister = scopeTab === 'shared' && pageView === 'register' && canWrite
  const isSystemRegister = scopeTab === 'system' && pageView === 'register' && isPlatformAdmin
  const isPersonalRegister = scopeTab === 'personal' && pageView === 'register'

  const handleScopeTabsChange = useCallback(
    (v: string): void => {
      if (isGatewayScopeTabValue(v, { allowSystem: true })) {
        startTransition(() => {
          setScopeTab(v)
        })
      }
    },
    [setScopeTab]
  )

  useEffect(() => {
    let needsUpdate = false
    const next = new URLSearchParams(searchParams)

    if (searchParams.get('wizard') === '1') {
      next.delete('wizard')
      next.set('tab', 'shared')
      next.set('view', 'register')
      needsUpdate = true
    }

    if (pageView === 'register' && scopeTab === 'shared' && !canWrite) {
      next.delete('view')
      needsUpdate = true
    }

    if (pageView === 'register' && scopeTab === 'system' && !isPlatformAdmin) {
      next.delete('view')
      needsUpdate = true
    }

    if (needsUpdate) {
      setSearchParams(next, { replace: true })
    }
  }, [searchParams, setSearchParams, pageView, scopeTab, canWrite, isPlatformAdmin])

  const teamListBackHref =
    scopeTab === 'system'
      ? systemModelsFilteredHref(teamId, credentialId || undefined)
      : teamModelsFilteredHref(teamId, credentialId || undefined)
  const personalListBackHref = personalModelsIndexHref(teamId)

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">模型</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {scopeTab === 'system' ? (
            isPlatformAdmin ? (
              <>
                系统级模型挂载在{' '}
                <Link
                  to={credentialsSystemBrowseIndexHref(teamId)}
                  className="text-primary underline-offset-4 hover:underline"
                >
                  系统凭据
                </Link>
                上；对外暴露名在{' '}
                <Link
                  to="/gateway/routes"
                  className="text-primary underline-offset-4 hover:underline"
                >
                  虚拟路由
                </Link>{' '}
                编排。
              </>
            ) : (
              <>
                系统预置、当前工作区可请求的模型（只读）。通过{' '}
                <Link
                  to="/gateway/keys"
                  className="text-primary underline-offset-4 hover:underline"
                >
                  虚拟 Key
                </Link>{' '}
                或{' '}
                <Link
                  to="/gateway/guide"
                  className="text-primary underline-offset-4 hover:underline"
                >
                  调用指南
                </Link>{' '}
                调用；团队自注册别名见「团队」Tab。
              </>
            )
          ) : scopeTab === 'shared' ? (
            <>
              团队自注册别名映射至 LiteLLM 上游；系统预置模型见{' '}
              <Link
                to={systemModelsBrowseIndexHref(teamId)}
                className="text-primary underline-offset-4 hover:underline"
              >
                系统
              </Link>{' '}
              Tab 或{' '}
              <Link to="/gateway/guide" className="text-primary underline-offset-4 hover:underline">
                调用指南
              </Link>
              。对外暴露名在{' '}
              <Link
                to="/gateway/routes"
                className="text-primary underline-offset-4 hover:underline"
              >
                虚拟路由
              </Link>{' '}
              编排。点击列表项进入详情；注册新模型请使用「添加模型」。
            </>
          ) : (
            <>
              个人模型进入 LiteLLM Router；对外暴露名可在{' '}
              <Link
                to="/gateway/routes"
                className="text-primary underline-offset-4 hover:underline"
              >
                虚拟路由
              </Link>{' '}
              编排，经{' '}
              <Link to="/gateway/keys" className="text-primary underline-offset-4 hover:underline">
                虚拟 Key
              </Link>{' '}
              / OpenAI 兼容 API 调用。点击列表进入详情；需先配置{' '}
              <Link
                to="/gateway/credentials?tab=personal"
                className="text-primary underline-offset-4 hover:underline"
              >
                个人凭据
              </Link>
              。
            </>
          )}
        </p>
      </div>

      <Tabs value={scopeTab} onValueChange={handleScopeTabsChange}>
        <TabsList>
          <GatewayScopeTabTriggers showSystemTab />
        </TabsList>

        {scopeTab === 'personal' ? (
          isPersonalRegister ? (
            <TabsContent value="personal" className="mt-4 space-y-4 focus-visible:outline-none">
              <Button variant="ghost" size="sm" className="h-8" asChild>
                <Link
                  to={personalListBackHref}
                  onMouseEnter={preloadPersonalModelsWorkspace}
                  onFocus={preloadPersonalModelsWorkspace}
                >
                  <ChevronLeft className="mr-1 h-4 w-4" />
                  返回模型列表
                </Link>
              </Button>
              <Suspense fallback={<ModelsPanelFallback />}>
                <PersonalModelsWorkspace pageView="register" />
              </Suspense>
            </TabsContent>
          ) : (
            <TabsContent value="personal" className="mt-4 focus-visible:outline-none">
              <Suspense fallback={<ModelsPanelFallback />}>
                <PersonalModelsWorkspace />
              </Suspense>
            </TabsContent>
          )
        ) : scopeTab === 'system' ? (
          isPlatformAdmin ? (
            isSystemRegister ? (
              <TabsContent value="system" className="mt-4 space-y-4 focus-visible:outline-none">
                <Button variant="ghost" size="sm" className="h-8" asChild>
                  <Link
                    to={teamListBackHref}
                    onMouseEnter={preloadTeamModelsWorkspace}
                    onFocus={preloadTeamModelsWorkspace}
                  >
                    <ChevronLeft className="mr-1 h-4 w-4" />
                    返回模型列表
                  </Link>
                </Button>
                <Suspense fallback={<ModelsPanelFallback />}>
                  <TeamModelsWorkspace pageView="register" hideRegisterAction listMode="system" />
                </Suspense>
              </TabsContent>
            ) : (
              <TabsContent value="system" className="mt-4 focus-visible:outline-none">
                <Suspense fallback={<ModelsPanelFallback />}>
                  <TeamModelsWorkspace listMode="system" />
                </Suspense>
              </TabsContent>
            )
          ) : (
            <TabsContent value="system" className="mt-4 focus-visible:outline-none">
              <Suspense fallback={<ModelsPanelFallback />}>
                <SystemModelsBrowseWorkspace />
              </Suspense>
            </TabsContent>
          )
        ) : isTeamRegister ? (
          <TabsContent value="shared" className="mt-4 space-y-4 focus-visible:outline-none">
            <Button variant="ghost" size="sm" className="h-8" asChild>
              <Link
                to={teamListBackHref}
                onMouseEnter={preloadTeamModelsWorkspace}
                onFocus={preloadTeamModelsWorkspace}
              >
                <ChevronLeft className="mr-1 h-4 w-4" />
                返回模型列表
              </Link>
            </Button>
            <Suspense fallback={<ModelsPanelFallback />}>
              <TeamModelsWorkspace pageView="register" hideRegisterAction />
            </Suspense>
          </TabsContent>
        ) : (
          <TabsContent value="shared" className="mt-4 focus-visible:outline-none">
            <Suspense fallback={<ModelsPanelFallback />}>
              <TeamModelsWorkspace listMode="team" />
            </Suspense>
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}
