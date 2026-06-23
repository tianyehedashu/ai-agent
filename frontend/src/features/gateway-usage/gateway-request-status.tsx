import { Badge } from '@/components/ui/badge'
import { AlertCircle, CheckCircle2, XCircle } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

/** 与后端 RequestStatus 对齐 */
export type GatewayRequestStatus =
  | 'success'
  | 'failed'
  | 'rate_limited'
  | 'budget_exceeded'
  | 'guardrail_blocked'

export const GATEWAY_REQUEST_STATUS_FILTER_OPTIONS: readonly {
  value: string
  label: string
}[] = [
  { value: 'all', label: '全部状态' },
  { value: 'success', label: '成功' },
  { value: 'failed', label: '失败' },
  { value: 'rate_limited', label: '限流' },
  { value: 'budget_exceeded', label: '配额超限' },
  { value: 'guardrail_blocked', label: '安全拦截' },
]

export const GATEWAY_REQUEST_STATUS_VALUE_OPTIONS = GATEWAY_REQUEST_STATUS_FILTER_OPTIONS.filter(
  (option) => option.value !== 'all'
)

const STATUS_LABELS: Record<GatewayRequestStatus, string> = {
  success: '成功',
  failed: '失败',
  rate_limited: '限流',
  budget_exceeded: '配额超限',
  guardrail_blocked: '安全拦截',
}

export function isGatewayRequestStatus(value: string): value is GatewayRequestStatus {
  return value in STATUS_LABELS
}

export function gatewayRequestStatusLabel(status: string): string {
  const normalized = status.toLowerCase()
  if (isGatewayRequestStatus(normalized)) {
    return STATUS_LABELS[normalized]
  }
  return status
}

export function usageStatsStatusRowLabel(groupKey: string, fallbackLabel?: string): string {
  const key = groupKey.trim().toLowerCase()
  if (isGatewayRequestStatus(key)) {
    return STATUS_LABELS[key]
  }
  const fallback = fallbackLabel?.trim()
  if (fallback && isGatewayRequestStatus(fallback.toLowerCase())) {
    return STATUS_LABELS[fallback.toLowerCase() as GatewayRequestStatus]
  }
  return fallback ?? groupKey
}

export function GatewayRequestStatusBadge({
  status,
}: Readonly<{ status: string }>): React.JSX.Element {
  const normalized = status.toLowerCase()
  const isSuccess = normalized === 'success'
  const isFailure = normalized === 'failed' || normalized === 'error'
  const Icon = isSuccess ? CheckCircle2 : isFailure ? XCircle : AlertCircle
  const label = gatewayRequestStatusLabel(normalized)

  return (
    <Badge
      variant="outline"
      className={cn(
        'inline-flex min-w-[76px] justify-center gap-1 border px-2 py-0.5 font-medium',
        isSuccess
          ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300'
          : isFailure
            ? 'border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300'
            : 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300'
      )}
    >
      <Icon className="h-3 w-3" />
      {label}
    </Badge>
  )
}
