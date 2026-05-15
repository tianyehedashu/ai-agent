/**
 * AI Gateway · 注册模型（个人 / 团队）
 */

import { Link } from 'react-router-dom'

import { ScrollArea } from '@/components/ui/scroll-area'
import { GatewayScopeTabs } from '@/features/gateway-models/gateway-scope-tabs'
import { PersonalModelsPanel } from '@/features/gateway-models/personal-models-panel'
import { TeamModelsWorkspace } from '@/features/gateway-models/team/team-models-workspace'
import { useGatewayScopeTab } from '@/hooks/use-gateway-scope-tab'

export default function GatewayModelsPage(): React.JSX.Element {
  const scopeTab = useGatewayScopeTab()

  return (
    <ScrollArea className="h-full">
      <div className="space-y-4 p-1">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">注册模型</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              团队模型进入 LiteLLM Router；个人模型用于 BYOK 对话。虚拟对外名请配置{' '}
              <Link
                to="/gateway/routes"
                className="text-primary underline-offset-4 hover:underline"
              >
                虚拟路由
              </Link>
              。
            </p>
          </div>
          <GatewayScopeTabs />
        </div>

        {scopeTab === 'personal' ? <PersonalModelsPanel /> : <TeamModelsWorkspace />}
      </div>
    </ScrollArea>
  )
}
