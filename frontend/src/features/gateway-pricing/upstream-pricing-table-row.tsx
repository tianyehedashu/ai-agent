import { memo, useCallback } from 'react'
import type React from 'react'

import type { UpstreamPricingRow } from '@/api/gateway/pricing'
import { Button } from '@/components/ui/button'
import { providerLabel } from '@/features/gateway-credentials/provider-schemas'
import { formatRateLine } from '@/features/gateway-pricing/format'
import { Pencil } from '@/lib/lucide-icons'

import { UPSTREAM_DISPLAY_CURRENCY } from './upstream-pricing-view'

export const UpstreamPricingTableRow = memo(function UpstreamPricingTableRow({
  row,
  onEdit,
}: Readonly<{
  row: UpstreamPricingRow
  onEdit: (row: UpstreamPricingRow) => void
}>): React.JSX.Element {
  const handleEdit = useCallback(() => {
    onEdit(row)
  }, [onEdit, row])

  return (
    <tr className="cv-auto-row border-t">
      <td className="px-3 py-2">{providerLabel(row.provider)}</td>
      <td className="px-3 py-2 font-mono text-xs">{row.upstream_model}</td>
      <td className="px-3 py-2 tabular-nums">
        {formatRateLine(
          row.input_cost_per_million_display,
          row.output_cost_per_million_display,
          UPSTREAM_DISPLAY_CURRENCY
        )}
      </td>
      <td className="px-3 py-2 text-muted-foreground">{row.source}</td>
      <td className="px-3 py-2 text-right">
        <Button type="button" variant="ghost" size="sm" onClick={handleEdit}>
          <Pencil className="mr-1.5 h-4 w-4" aria-hidden="true" />
          调价
        </Button>
      </td>
    </tr>
  )
})
