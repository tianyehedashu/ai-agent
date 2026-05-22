/**
 * 个人 / 团队 / 系统 Scope（凭据页、模型页共用）
 *
 * `personal` / `shared` 与后端 `Team.kind` 对齐；`system` 为系统注册表 Tab。
 * 模型页、凭据页内 `showSystemTab` 均为 true；侧栏「系统凭据/模型」快捷入口仍仅平台管理员。
 */

import type React from 'react'
import { startTransition } from 'react'

import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { isGatewayScopeTabValue } from '@/features/gateway-models/constants'
import { useGatewayScopeTab } from '@/hooks/use-gateway-scope-tab'

/** 置于父级 `<Tabs>` 内，仅渲染触发器。 */
export function GatewayScopeTabTriggers({
  showSystemTab = false,
}: Readonly<{ showSystemTab?: boolean }>): React.ReactElement {
  return (
    <>
      <TabsTrigger value="personal">个人</TabsTrigger>
      <TabsTrigger value="shared">团队</TabsTrigger>
      {showSystemTab ? <TabsTrigger value="system">系统</TabsTrigger> : null}
    </>
  )
}

interface GatewayScopeTabsProps {
  teamHint?: React.ReactNode
}

/** 独立 Scope 切换（无 TabsContent）；复杂页面请用 hook + `GatewayScopeTabTriggers`。 */
export function GatewayScopeTabs({
  teamHint,
  showSystemTab = false,
}: GatewayScopeTabsProps & { showSystemTab?: boolean }): React.ReactElement {
  const { scopeTab, setScopeTab } = useGatewayScopeTab({ allowSystemTab: showSystemTab })

  return (
    <div className="flex flex-col gap-1">
      <Tabs
        value={scopeTab}
        onValueChange={(v) => {
          if (isGatewayScopeTabValue(v, { allowSystem: showSystemTab })) {
            startTransition(() => {
              setScopeTab(v)
            })
          }
        }}
      >
        <TabsList>
          <GatewayScopeTabTriggers showSystemTab={showSystemTab} />
        </TabsList>
      </Tabs>
      {scopeTab === 'shared' && teamHint ? (
        <p className="text-sm text-muted-foreground">{teamHint}</p>
      ) : null}
    </div>
  )
}
