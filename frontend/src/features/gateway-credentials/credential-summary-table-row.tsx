/**
 * 凭据摘要只读行（成员可见的系统凭据等，无密钥与操作）。
 */

import type React from 'react'

import type { CredentialSummary } from '@/api/gateway'
import { Badge } from '@/components/ui/badge'
import { CredentialAffiliationCell } from '@/features/gateway-credentials/components/credential-affiliation-cell'
import { CredentialProviderCell } from '@/features/gateway-credentials/components/credential-provider-cell'
import { providerLabel } from '@/features/gateway-credentials/provider-schemas'

export interface CredentialSummaryTableRowProps {
  summary: CredentialSummary
  teamNameById: Map<string, string>
}

export function CredentialSummaryTableRow({
  summary,
  teamNameById,
}: CredentialSummaryTableRowProps): React.JSX.Element {
  return (
    <tr className="border-b last:border-0 hover:bg-muted/20" data-credential-id={summary.id}>
      <td className="px-4 py-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{summary.name}</span>
          {summary.is_config_managed ? (
            <Badge variant="secondary" className="text-[10px] font-normal">
              配置同步
            </Badge>
          ) : null}
          {summary.management_access === 'metadata' ? (
            <Badge variant="outline" className="text-[10px] font-normal">
              只读
            </Badge>
          ) : null}
        </div>
      </td>
      <td className="px-4 py-2 font-mono text-xs text-muted-foreground">—</td>
      <td className="px-4 py-2 text-xs">
        <div className="flex flex-col">
          <span className="font-medium">{providerLabel(summary.provider)}</span>
          <span className="font-mono text-[10px] text-muted-foreground" title={summary.provider}>
            {summary.provider}
          </span>
        </div>
      </td>
      <td className="px-4 py-2">
        <CredentialAffiliationCell scope={summary.scope} teamNameById={teamNameById} compact />
      </td>
      <td className="px-4 py-2">
        <CredentialProviderCell credential={summary} />
      </td>
      <td className="px-4 py-2">
        <Badge
          variant={summary.is_active ? 'secondary' : 'outline'}
          className="text-[10px] font-normal"
        >
          {summary.is_active ? '启用' : '停用'}
        </Badge>
      </td>
      <td className="px-4 py-2" />
    </tr>
  )
}
