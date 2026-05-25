import type React from 'react'

import type { DownstreamPricingRow } from '@/api/gateway'
import { providerLabel } from '@/features/gateway-credentials/provider-schemas'

function shortenId(id: string): string {
  if (id.length <= 12) return id
  return `${id.slice(0, 8)}…${id.slice(-4)}`
}

export function PricingModelLabel({
  row,
}: Readonly<{ row: DownstreamPricingRow }>): React.JSX.Element {
  if (!row.gateway_model_id) {
    return <span className="text-muted-foreground">团队默认</span>
  }

  const trimmed = row.model_name?.trim()
  const displayName = trimmed && trimmed.length > 0 ? trimmed : '未知模型'

  return (
    <div className="space-y-0.5">
      <div className="font-medium">{displayName}</div>
      <div className="font-mono text-xs text-muted-foreground" title={row.gateway_model_id}>
        {shortenId(row.gateway_model_id)}
      </div>
    </div>
  )
}

export function PricingCredentialLabel({
  row,
}: Readonly<{ row: DownstreamPricingRow }>): React.JSX.Element {
  if (!row.gateway_model_id) {
    return <span className="text-muted-foreground">—</span>
  }

  if (!row.provider && !row.credential_name) {
    return <span className="text-muted-foreground">—</span>
  }

  const provider = row.provider ? providerLabel(row.provider) : null
  const cred = row.credential_name?.trim()

  if (provider && cred) {
    return (
      <span>
        {provider} · {cred}
      </span>
    )
  }

  return <span>{provider ?? cred ?? '—'}</span>
}
