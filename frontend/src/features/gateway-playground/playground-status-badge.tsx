import type React from 'react'

import { Badge } from '@/components/ui/badge'
import { Loader2 } from '@/lib/lucide-icons'

import type { PlaygroundStatus } from './types'

export function PlaygroundStatusBadge({
  status,
}: Readonly<{ status: PlaygroundStatus }>): React.JSX.Element | null {
  if (status === 'idle') return null
  if (status === 'pending') {
    return (
      <Badge variant="secondary" className="gap-1">
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
        请求中
      </Badge>
    )
  }
  if (status === 'streaming') {
    return (
      <Badge variant="secondary" className="gap-1">
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
        流式接收中
      </Badge>
    )
  }
  if (status === 'done') {
    return <Badge variant="default">完成</Badge>
  }
  return <Badge variant="destructive">失败</Badge>
}
