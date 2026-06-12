import { Loader2 } from '@/lib/lucide-icons'

export function ModelDetailLoadingState({
  label = '加载模型…',
}: {
  label?: string
}): React.JSX.Element {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />
      {label}
    </div>
  )
}

export function ModelDetailNotFoundState({
  message = '未找到该模型，可能已被删除或你无权访问。',
}: {
  message?: string
}): React.JSX.Element {
  return <p className="py-12 text-center text-sm text-muted-foreground">{message}</p>
}
