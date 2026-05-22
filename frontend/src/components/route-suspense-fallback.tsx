import { Loader2 } from '@/lib/lucide-icons'

/** 路由 lazy chunk 加载时的占位 */
export function RouteSuspenseFallback(): React.JSX.Element {
  return (
    <div
      className="flex flex-1 items-center justify-center py-16"
      role="status"
      aria-live="polite"
      aria-label="页面加载中"
    >
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  )
}
