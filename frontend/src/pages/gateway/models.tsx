/**
 * AI Gateway · 模型（个人 / 团队）
 */

import { Suspense, lazy, useCallback, useEffect } from 'react'

import { ChevronLeft, Loader2 } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  type ModelScopeTab,
  parseModelsPageView,
  parseScopeTab,
} from '@/features/gateway-models/constants'
import { personalModelsIndexHref, teamModelsFilteredHref } from '@/features/gateway-models/paths'
import { preloadPersonalModelsWorkspace } from '@/features/gateway-models/personal/personal-model-preload'
import { preloadTeamModelsWorkspace } from '@/features/gateway-models/team/preloads'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'

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
  const [searchParams, setSearchParams] = useSearchParams()
  const scopeTab = parseScopeTab(searchParams.get('tab'))
  const pageView = parseModelsPageView(searchParams.get('view'))
  const credentialId = searchParams.get('credentialId') ?? ''
  const { canWrite } = useGatewayPermission()
  const isTeamRegister = scopeTab === 'team' && pageView === 'register' && canWrite
  const isPersonalRegister = scopeTab === 'personal' && pageView === 'register'

  const setScopeTab = useCallback(
    (next: ModelScopeTab): void => {
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev)
          n.set('tab', next)
          n.delete('view')
          if (next === 'team') {
            // keep credentialId for team
          } else {
            n.delete('credentialId')
            n.delete('modelId')
          }
          return n
        },
        { replace: true }
      )
    },
    [setSearchParams]
  )

  const handleScopeTabsChange = useCallback(
    (v: string): void => {
      if (v === 'personal' || v === 'team') setScopeTab(v)
    },
    [setScopeTab]
  )

  useEffect(() => {
    const raw = searchParams.get('tab')
    if (raw !== null && raw !== 'personal' && raw !== 'team') {
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev)
          n.set('tab', 'team')
          return n
        },
        { replace: true }
      )
    }
  }, [searchParams, setSearchParams])

  useEffect(() => {
    if (searchParams.get('wizard') !== '1') return
    setSearchParams(
      (prev) => {
        const n = new URLSearchParams(prev)
        n.delete('wizard')
        n.set('tab', 'team')
        n.set('view', 'register')
        return n
      },
      { replace: true }
    )
  }, [searchParams, setSearchParams])

  useEffect(() => {
    if (pageView === 'register' && scopeTab === 'team' && !canWrite) {
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev)
          n.delete('view')
          return n
        },
        { replace: true }
      )
    }
  }, [pageView, scopeTab, canWrite, setSearchParams])

  const teamListBackHref = teamModelsFilteredHref(credentialId || undefined)
  const personalListBackHref = personalModelsIndexHref()

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">模型</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {scopeTab === 'team' ? (
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
              个人模型进入 LiteLLM Router，可用于对话与{' '}
              <Link to="/gateway/keys" className="text-primary underline-offset-4 hover:underline">
                虚拟 Key
              </Link>{' '}
              / OpenAI 兼容 API。点击列表进入详情；需先配置{' '}
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
          <TabsTrigger value="personal">个人</TabsTrigger>
          <TabsTrigger value="team">团队</TabsTrigger>
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
          <TabsContent value="team" className="mt-4 space-y-4 focus-visible:outline-none">
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
          <TabsContent value="team" className="mt-4 focus-visible:outline-none">
            <Suspense fallback={<ModelsPanelFallback />}>
              <TeamModelsWorkspace />
            </Suspense>
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}
