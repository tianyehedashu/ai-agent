import { CheckCircle2, CircleDot, TerminalSquare, Text, TriangleAlert } from 'lucide-react'

import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type { ProcessEvent, ProcessEventKind } from '@/types'

interface ProcessPanelProps {
  events: ProcessEvent[]
}

type IconType = (props: { className?: string }) => React.JSX.Element

const kindMeta = {
  thinking: { label: 'thinking', icon: CircleDot as IconType, color: 'text-purple-500' },
  text: { label: 'text', icon: Text as IconType, color: 'text-slate-500' },
  tool_call: { label: 'tool_call', icon: TerminalSquare as IconType, color: 'text-blue-500' },
  tool_result: { label: 'tool_result', icon: CheckCircle2 as IconType, color: 'text-emerald-500' },
  done: { label: 'done', icon: CheckCircle2 as IconType, color: 'text-primary' },
  error: { label: 'error', icon: TriangleAlert as IconType, color: 'text-red-500' },
  interrupt: { label: 'interrupt', icon: TriangleAlert as IconType, color: 'text-yellow-500' },
} satisfies Record<ProcessEventKind, { label: string; icon: IconType; color: string }>

function getEventTitle(event: ProcessEvent): string {
  const payload = event.payload
  if (event.kind === 'tool_call') {
    const name = payload.name
    return typeof name === 'string' && name ? name : 'tool_call'
  }
  if (event.kind === 'tool_result') {
    const success = payload.success
    return success === true ? 'tool_result: success' : 'tool_result: failed'
  }
  return kindMeta[event.kind].label
}

function getEventPreview(event: ProcessEvent): string | null {
  const payload = event.payload
  if (event.kind === 'text') {
    const content = payload.content
    return typeof content === 'string' ? content : null
  }
  if (event.kind === 'error') {
    const error = payload.error
    return typeof error === 'string' ? error : null
  }
  return null
}

export function ProcessPanel({ events }: Readonly<ProcessPanelProps>): React.JSX.Element {
  return (
    <Card className="mt-3 border-muted/60 bg-muted/30">
      <div className="flex items-center justify-between px-3 py-2">
        <span className="text-xs font-semibold text-muted-foreground">全过程</span>
        <span className="text-xs text-muted-foreground">{events.length} events</span>
      </div>
      <div className="space-y-2 px-3 pb-3">
        {events.map((event, index) => {
          const meta = kindMeta[event.kind]
          const Icon = meta.icon
          const preview = getEventPreview(event)
          return (
            <div key={event.id} className="flex items-start gap-3">
              <div className="relative flex h-5 w-5 items-center justify-center">
                <Icon className={cn('h-4 w-4', meta.color)} />
                {index < events.length - 1 && (
                  <span className="absolute top-5 h-3 w-px bg-border" aria-hidden />
                )}
              </div>
              <div className="flex-1 rounded-md border border-border/60 bg-background/70 px-2 py-1">
                <div className="text-xs font-medium text-foreground">{getEventTitle(event)}</div>
                {preview ? (
                  <div className="mt-1 text-xs text-muted-foreground">{preview}</div>
                ) : null}
              </div>
            </div>
          )
        })}
      </div>
    </Card>
  )
}
