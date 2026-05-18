/**
 * 个人 / 团队 Scope（凭据页、模型页共用）
 *
 * URL 字面量与后端 `Team.kind` 对齐：`personal` / `shared`。
 * 旧 `?tab=team` 由 `useGatewayScopeTab` 迁移为 `shared`。
 */

import type React from 'react'
import { startTransition } from 'react'

import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useGatewayScopeTab } from '@/hooks/use-gateway-scope-tab'

/** 置于父级 `<Tabs>` 内，仅渲染触发器。 */
export function GatewayScopeTabTriggers(): React.ReactElement {
  return (
    <>
      <TabsTrigger value="personal">个人</TabsTrigger>
      <TabsTrigger value="shared">团队</TabsTrigger>
    </>
  )
}

interface GatewayScopeTabsProps {
  teamHint?: React.ReactNode
}

/** 独立 Scope 切换（无 TabsContent）；复杂页面请用 hook + `GatewayScopeTabTriggers`。 */
export function GatewayScopeTabs({ teamHint }: GatewayScopeTabsProps): React.ReactElement {
  const { scopeTab, setScopeTab } = useGatewayScopeTab()

  return (
    <div className="flex flex-col gap-1">
      <Tabs
        value={scopeTab}
        onValueChange={(v) => {
          if (v === 'personal' || v === 'shared') {
            startTransition(() => {
              setScopeTab(v)
            })
          }
        }}
      >
        <TabsList>
          <GatewayScopeTabTriggers />
        </TabsList>
      </Tabs>
      {scopeTab === 'shared' && teamHint ? (
        <p className="text-sm text-muted-foreground">{teamHint}</p>
      ) : null}
    </div>
  )
}
