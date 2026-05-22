/**
 * 系统预置可请求模型（只读）：系统 Tab 下展示 registry_kind=system 行。
 */

import { memo } from 'react'

import { Link } from 'react-router-dom'

import type { GatewayModel } from '@/api/gateway'
import { ModelStatusBadge } from '@/components/model-status-badge'
import { Badge } from '@/components/ui/badge'

import { ModelCapabilityBadges } from '../team/model-capability-badges'

interface SystemCallableModelsListProps {
  models: GatewayModel[]
}

export const SystemCallableModelsList = memo(function SystemCallableModelsList({
  models,
}: SystemCallableModelsListProps): React.JSX.Element {
  return (
    <div className="space-y-3 rounded-lg border bg-muted/20 p-4">
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold">系统模型</h3>
          <Badge variant="secondary" className="text-xs font-normal">
            只读 · {models.length} 个可请求
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          以下模型由系统预置，可直接通过{' '}
          <Link to="/gateway/keys" className="text-primary underline-offset-4 hover:underline">
            虚拟 Key
          </Link>{' '}
          或{' '}
          <Link to="/gateway/guide" className="text-primary underline-offset-4 hover:underline">
            调用指南
          </Link>{' '}
          使用。如需管理团队自注册别名，请切换到「团队」Tab 并注册模型。
        </p>
      </div>
      <ul className="divide-y rounded-md border bg-card">
        {models.map((model) => (
          <li key={model.id} className="flex flex-wrap items-center gap-2 px-3 py-2.5">
            <span className="min-w-0 flex-1 truncate font-mono text-sm font-medium">
              {model.name}
            </span>
            <ModelCapabilityBadges model={model} />
            <ModelStatusBadge
              status={model.last_test_status}
              testedAt={model.last_tested_at}
              reason={model.last_test_reason}
              compact
            />
          </li>
        ))}
      </ul>
    </div>
  )
})
