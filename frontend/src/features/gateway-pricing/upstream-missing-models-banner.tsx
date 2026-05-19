import { memo } from 'react'
import type React from 'react'

import { providerLabel } from '@/features/gateway-credentials/provider-schemas'

import type { ModelMissingUpstream } from './upstream-pricing-view'

const PREVIEW_LIMIT = 12

export const UpstreamMissingModelsBanner = memo(function UpstreamMissingModelsBanner({
  items,
}: Readonly<{
  items: readonly ModelMissingUpstream[]
}>): React.JSX.Element {
  const preview = items.slice(0, PREVIEW_LIMIT)
  const overflow = items.length - PREVIEW_LIMIT

  return (
    <div className="rounded-md border border-amber-500/30 bg-amber-50/50 p-3 text-sm dark:bg-amber-950/20">
      <p className="font-medium text-amber-900 dark:text-amber-100">
        {items.length} 个已注册模型尚未配置上游成本
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        这些模型在结算时无法按价目表扣费。请执行「从 LiteLLM 同步」或手动补录。
      </p>
      <ul className="mt-2 max-h-32 space-y-1 overflow-y-auto text-xs">
        {preview.map((item) => (
          <li key={`${item.gatewayName}-${item.upstreamModel}`}>
            <span className="font-medium">{item.gatewayName}</span>
            <span className="ml-2 font-mono text-muted-foreground">
              {providerLabel(item.provider)} · {item.upstreamModel}
            </span>
          </li>
        ))}
      </ul>
      {overflow > 0 ? (
        <p className="mt-1 text-xs text-muted-foreground">另有 {overflow} 个未列出</p>
      ) : null}
    </div>
  )
})
