import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { formatGatewayQueryError } from '@/lib/gateway-api-error'

export function GatewayQueryErrorBanner({
  error,
  title = '加载失败',
  fallback,
}: Readonly<{
  error: unknown
  title?: string
  fallback?: string
}>): React.JSX.Element | null {
  if (!error) return null
  return (
    <Alert variant="destructive">
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{formatGatewayQueryError(error, fallback)}</AlertDescription>
    </Alert>
  )
}
