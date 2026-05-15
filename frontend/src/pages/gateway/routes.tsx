/**
 * AI Gateway · 虚拟路由
 */

import { RouteWorkspace } from '@/features/gateway-models/routes/route-workspace'

export default function GatewayRoutesPage(): React.JSX.Element {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">虚拟路由</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          将注册模型编排为对外暴露的 model 名，供虚拟 Key 与 SDK 调用。
        </p>
      </div>
      <RouteWorkspace />
    </div>
  )
}
