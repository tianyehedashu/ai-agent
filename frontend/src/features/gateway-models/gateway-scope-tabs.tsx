/**
 * 个人 / 团队 Scope（凭据页、模型页共用模式）
 */

import type React from 'react'
import { useCallback, useEffect } from 'react'

import { useSearchParams } from 'react-router-dom'

import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

import { type ModelScopeTab, parseScopeTab } from './constants'

interface GatewayScopeTabsProps {
  teamHint?: React.ReactNode
}

export function GatewayScopeTabs({ teamHint }: GatewayScopeTabsProps): React.ReactElement {
  const [searchParams, setSearchParams] = useSearchParams()
  const scopeTab = parseScopeTab(searchParams.get('tab'))

  const setScopeTab = useCallback(
    (next: ModelScopeTab): void => {
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev)
          n.set('tab', next)
          return n
        },
        { replace: true }
      )
    },
    [setSearchParams]
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

  return (
    <div className="flex flex-col gap-1">
      <Tabs
        value={scopeTab}
        onValueChange={(v) => {
          if (v === 'personal' || v === 'team') setScopeTab(v)
        }}
      >
        <TabsList>
          <TabsTrigger value="personal">个人</TabsTrigger>
          <TabsTrigger value="team">团队</TabsTrigger>
        </TabsList>
      </Tabs>
      {scopeTab === 'team' && teamHint ? (
        <p className="text-sm text-muted-foreground">{teamHint}</p>
      ) : null}
    </div>
  )
}
