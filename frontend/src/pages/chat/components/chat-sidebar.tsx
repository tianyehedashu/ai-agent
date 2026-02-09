import { useState, useMemo } from 'react'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Trash2,
  MoreVertical,
  Loader2,
  MessageCircle,
  PanelLeftClose,
  PanelLeftOpen,
  MessageSquarePlus,
} from 'lucide-react'
import { Link, useParams, useNavigate } from 'react-router-dom'

import { sessionApi } from '@/api/session'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { useToast } from '@/hooks/use-toast'
import { groupSessionsByDate } from '@/lib/session-utils'
import { cn, formatRelativeTime } from '@/lib/utils'
import { useChatStore } from '@/stores/chat'
import type { Session } from '@/types'

export default function ChatSidebar(): React.JSX.Element {
  const { sessionId } = useParams<{ sessionId?: string }>()
  const navigate = useNavigate()
  const [isCollapsed, setIsCollapsed] = useState(false)

  const { data: sessionsData, isLoading } = useQuery({
    queryKey: ['sessions'],
    queryFn: () => sessionApi.list(1, 50),
  })

  const sessions = useMemo(() => sessionsData?.items ?? [], [sessionsData?.items])

  const groupedSessions = useMemo(
    () => groupSessionsByDate(sessions),
    [sessions]
  )

  // 新建对话：仅导航到无 sessionId 的聊天页，会话在用户发送第一条消息时由后端创建（避免空会话入库）
  const handleCreateSession = (): void => {
    navigate('/chat')
  }

  return (
    <TooltipProvider delayDuration={0}>
      <div
        className={cn(
          'relative flex shrink-0 flex-col border-r border-border/40 bg-background/95 backdrop-blur transition-all duration-300 ease-in-out supports-[backdrop-filter]:bg-background/60',
          isCollapsed ? 'w-[70px]' : 'w-[280px]'
        )}
      >
        {/* Header */}
        <div
          className={cn(
            'flex items-center p-4',
            isCollapsed ? 'justify-center' : 'justify-between'
          )}
        >
          {!isCollapsed && <span className="text-sm font-semibold tracking-tight">历史记录</span>}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-muted-foreground hover:text-foreground"
                onClick={() => {
                  setIsCollapsed(!isCollapsed)
                }}
              >
                {isCollapsed ? (
                  <PanelLeftOpen className="h-4 w-4" />
                ) : (
                  <PanelLeftClose className="h-4 w-4" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">
              {isCollapsed ? '展开侧边栏' : '收起侧边栏'}
            </TooltipContent>
          </Tooltip>
        </div>

        {/* New Chat Button */}
        <div className={cn('px-3 pb-4', isCollapsed && 'px-2')}>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                onClick={handleCreateSession}
                variant={isCollapsed ? 'outline' : 'default'}
                size={isCollapsed ? 'icon' : 'default'}
                className={cn(
                  'w-full shadow-sm transition-all hover:shadow-md',
                  isCollapsed ? 'h-10 w-10 rounded-full p-0' : 'justify-start gap-2'
                )}
              >
                <MessageSquarePlus className="h-4 w-4" />
                {!isCollapsed && <span className="font-medium">新建对话</span>}
              </Button>
            </TooltipTrigger>
            {isCollapsed && <TooltipContent side="right">新建对话</TooltipContent>}
          </Tooltip>
        </div>

        {/* Sessions List */}
        <ScrollArea className="flex-1 px-3">
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : sessions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <MessageCircle className="mb-3 h-10 w-10 text-muted-foreground/30" />
              {!isCollapsed && <p className="text-sm text-muted-foreground">暂无对话记录</p>}
            </div>
          ) : (
            <div className="space-y-6 pb-6">
              {Object.entries(groupedSessions).map(([groupName, groupSessions]) => {
                if (groupSessions.length === 0) return null
                return (
                  <div key={groupName} className={cn(isCollapsed && 'flex flex-col items-center')}>
                    {!isCollapsed && (
                      <h3 className="mb-2 px-2 text-xs font-medium text-muted-foreground/70">
                        {groupName}
                      </h3>
                    )}
                    {isCollapsed && <div className="mb-2 h-px w-8 bg-border/50" />}
                    <div className={cn('space-y-0.5', isCollapsed && 'space-y-2')}>
                      {groupSessions.map((session) => (
                        <SessionItem
                          key={session.id}
                          session={session}
                          isActive={session.id === sessionId}
                          isCollapsed={isCollapsed}
                          currentSessionId={sessionId}
                        />
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </ScrollArea>
      </div>
    </TooltipProvider>
  )
}

function SessionItem({
  session,
  isActive,
  isCollapsed,
  currentSessionId,
}: Readonly<{
  session: Session
  isActive: boolean
  isCollapsed: boolean
  currentSessionId?: string
}>): React.JSX.Element {
  const [isHovered, setIsHovered] = useState(false)
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { toast } = useToast()
  // 无标题时兜底：有视频任务的会话显示「新视频」，否则「新对话」
  const defaultTitle =
    (session.videoTaskCount ?? 0) > 0 ? '新视频' : '新对话'

  const handleDelete = async (e: React.MouseEvent): Promise<void> => {
    e.preventDefault()
    e.stopPropagation()

    if (confirm('确定要删除这个对话吗？')) {
      try {
        await sessionApi.delete(session.id)
        void queryClient.invalidateQueries({ queryKey: ['sessions'] })
        void queryClient.invalidateQueries({ queryKey: ['session', session.id] })
        toast({
          title: '删除成功',
          description: '会话已删除',
        })
        if (session.id === currentSessionId) {
          useChatStore.getState().setCurrentSession(null)
          useChatStore.getState().clearMessages()
          navigate('/chat')
        }
      } catch (error) {
        toast({
          variant: 'destructive',
          title: '删除失败',
          description: error instanceof Error ? error.message : '未知错误',
        })
      }
    }
  }

  const ItemContent = (
    <Link
      to={`/chat/${session.id}`}
      className={cn(
        'group flex items-center transition-all duration-200',
        isCollapsed ? 'h-10 w-10 justify-center rounded-full' : 'gap-2 rounded-md px-2 py-2.5',
        isActive
          ? 'bg-secondary text-foreground shadow-sm'
          : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground'
      )}
      onMouseEnter={() => {
        setIsHovered(true)
      }}
      onMouseLeave={() => {
        setIsHovered(false)
      }}
    >
      {isCollapsed ? (
        <MessageCircle className="h-5 w-5" />
      ) : (
        <>
          <div className="flex-1 overflow-hidden">
            <p className="truncate font-medium leading-none">{session.title ?? defaultTitle}</p>
            <p className="mt-1 truncate text-xs opacity-70">
              {formatRelativeTime(session.updatedAt)}
            </p>
          </div>

          {(isHovered || isActive) && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 opacity-0 transition-opacity group-hover:opacity-100 data-[state=open]:opacity-100"
                  onClick={(e) => {
                    e.preventDefault()
                  }}
                >
                  <MoreVertical className="h-3 w-3" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-40">
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive"
                  onClick={handleDelete}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  删除对话
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </>
      )}
    </Link>
  )

  if (isCollapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>{ItemContent}</TooltipTrigger>
        <TooltipContent side="right" className="max-w-[200px] truncate">
          {session.title ?? defaultTitle}
        </TooltipContent>
      </Tooltip>
    )
  }

  return ItemContent
}
