import { useState } from 'react'

import { useQuery } from '@tanstack/react-query'
import { Plus, MessageSquare, Trash2, MoreVertical } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { sessionApi } from '@/api/session'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn, formatRelativeTime } from '@/lib/utils'
import type { Session } from '@/types'

export default function ChatSidebar(): React.JSX.Element {
  const { sessionId } = useParams<{ sessionId?: string }>()

  const { data: sessionsData } = useQuery({
    queryKey: ['sessions'],
    queryFn: () => sessionApi.list(1, 50),
  })

  const sessions = sessionsData?.items ?? []

  return (
    <div className="flex w-64 flex-col border-r bg-card">
      {/* Header */}
      <div className="flex items-center justify-between border-b p-4">
        <h2 className="font-semibold">对话历史</h2>
        <Button variant="ghost" size="icon" asChild>
          <Link to="/chat">
            <Plus className="h-4 w-4" />
          </Link>
        </Button>
      </div>

      {/* Sessions List */}
      <ScrollArea className="flex-1">
        <div className="space-y-1 p-2">
          {sessions.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">暂无对话记录</p>
          ) : (
            sessions.map((session) => (
              <SessionItem key={session.id} session={session} isActive={session.id === sessionId} />
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  )
}

function SessionItem({
  session,
  isActive,
}: Readonly<{
  session: Session
  isActive: boolean
}>): React.JSX.Element {
  const [isHovered, setIsHovered] = useState(false)

  const handleDelete = async (): Promise<void> => {
    if (confirm('确定要删除这个对话吗？')) {
      try {
        await sessionApi.delete(session.id)
        // TODO: Refresh sessions list
      } catch (error) {
        console.error('Failed to delete session:', error)
      }
    }
  }

  return (
    <Link
      to={`/chat/${session.id}`}
      className={cn(
        'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
        isActive
          ? 'bg-primary/10 text-primary'
          : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
      )}
      onMouseEnter={() => {
        setIsHovered(true)
      }}
      onMouseLeave={() => {
        setIsHovered(false)
      }}
    >
      <MessageSquare className="h-4 w-4 flex-shrink-0" />
      <div className="flex-1 overflow-hidden">
        <p className="truncate">{session.title ?? `对话 ${session.id.slice(0, 8)}`}</p>
        <p className="text-xs text-muted-foreground">{formatRelativeTime(session.updatedAt)}</p>
      </div>

      {isHovered && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 opacity-0 group-hover:opacity-100"
              onClick={(e) => {
                e.preventDefault()
              }}
            >
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem
              className="text-destructive"
              onClick={(e) => {
                e.preventDefault()
                void handleDelete()
              }}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              删除
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </Link>
  )
}
