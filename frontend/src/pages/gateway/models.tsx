/**
 * AI Gateway · 模型（个人 / 团队）
 */

import { Suspense, lazy, startTransition, useCallback, useEffect } from 'react'

import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList } from '@/components/ui/tabs'
import { parseModelsPageView } from '@/features/gateway-models/constants'
import { GatewayScopeTabTriggers } from '@/features/gateway-models/gateway-scope-tabs'
import { personalModelsIndexHref, teamModelsFilteredHref } from '@/features/gateway-models/paths'
import { preloadPersonalModelsWorkspace } from '@/features/gateway-models/personal/personal-model-preload'
import { preloadTeamModelsWorkspace } from '@/features/gateway-models/team/preloads'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayScopeTab } from '@/hooks/use-gateway-scope-tab'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { ChevronLeft, Loader2 } from '@/lib/lucide-icons'

const PersonalModelsWorkspace = lazy(() =>
  import('@/features/gateway-models/personal/personal-models-workspace').then((m) => ({
    default: m.PersonalModelsWorkspace,
  }))
)

const TeamModelsWorkspace = lazy(() =>
  import('@/features/gateway-models/team/team-models-workspace').then((m) => ({
    default: m.TeamModelsWorkspace,
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
  const { scopeTab, setScopeTab, searchParams, setSearchParams } = useGatewayScopeTab({
    mutateParamsOnTabChange: (next, params) => {
      params.delete('view')
      if (next === 'personal') {
        params.delete('credentialId')
        params.delete('modelId')
      }
    },
  })
  const pageView = parseModelsPageView(searchParams.get('view'))
  const credentialId = searchParams.get('credentialId') ?? ''
  const { canWrite } = useGatewayPermission()
  const isTeamRegister = scopeTab === 'shared' && pageView === 'register' && canWrite
  const isPersonalRegister = scopeTab === 'personal' && pageView === 'register'

  const handleScopeTabsChange = useCallback(
    (v: string): void => {
      if (v === 'personal' || v === 'shared') {
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

    if (needsUpdate) {
      setSearchParams(next, { replace: true })
    }
  }, [searchParams, setSearchParams, pageView, scopeTab, canWrite])

  const teamListBackHref = teamModelsFilteredHref(teamId, credentialId || undefined)
  const personalListBackHref = personalModelsIndexHref(teamId)

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">模型</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {scopeTab === 'shared' ? (
            <>
              团队别名映射至 LiteLLM 上游；对外暴露名在{' '}
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
          <GatewayScopeTabTriggers />
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
              <TeamModelsWorkspace />
            </Suspense>
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}
