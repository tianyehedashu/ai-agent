import { useState, useMemo } from 'react'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, MoreVertical, Loader2, MessageCircle, PanelLeftClose, PanelLeftOpen, MessageSquarePlus } from 'lucide-react'
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useToast } from '@/hooks/use-toast'
import { cn, formatRelativeTime } from '@/lib/utils'
import type { Session } from '@/types'

// Group sessions by date
const groupSessions = (sessions: Session[]) => {
  const groups: Record<string, Session[]> = {
    '今天': [],
    '昨天': [],
    '过去7天': [],
    '更早': [],
  }

  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  const lastWeek = new Date(today)
  lastWeek.setDate(lastWeek.getDate() - 7)

  sessions.forEach((session) => {
    const date = new Date(session.updatedAt)
    if (date >= today) {
      groups['今天'].push(session)
    } else if (date >= yesterday) {
      groups['昨天'].push(session)
    } else if (date >= lastWeek) {
      groups['过去7天'].push(session)
    } else {
      groups['更早'].push(session)
    }
  })

  return groups
}

export default function ChatSidebar(): React.JSX.Element {
  const { sessionId } = useParams<{ sessionId?: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [isCollapsed, setIsCollapsed] = useState(false)

  const { data: sessionsData, isLoading } = useQuery({
    queryKey: ['sessions'],
    queryFn: () => sessionApi.list(1, 50),
  })

  const createMutation = useMutation({
    mutationFn: (options?: { agentId?: string; title?: string }) => sessionApi.create(options),
    onSuccess: (newSession) => {
      // 刷新会话列表
      void queryClient.invalidateQueries({ queryKey: ['sessions'] })
      // 导航到新会话页面
      navigate(`/chat/${newSession.id}`)
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: '创建会话失败',
        description: error instanceof Error ? error.message : '未知错误',
      })
    },
  })

  const sessions = sessionsData?.items ?? []
  
  const groupedSessions = useMemo(() => groupSessions(sessions), [sessions])

  const handleCreateSession = (): void => {
    void createMutation.mutateAsync({})
  }

  return (
    <TooltipProvider delayDuration={0}>
      <div 
        className={cn(
          "relative flex shrink-0 flex-col border-r border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 transition-all duration-300 ease-in-out",
          isCollapsed ? "w-[70px]" : "w-[280px]"
        )}
      >
        {/* Header */}
        <div className={cn("flex items-center p-4", isCollapsed ? "justify-center" : "justify-between")}>
          {!isCollapsed && <span className="text-sm font-semibold tracking-tight">历史记录</span>}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button 
                variant="ghost" 
                size="icon" 
                className="h-8 w-8 text-muted-foreground hover:text-foreground"
                onClick={() => setIsCollapsed(!isCollapsed)}
              >
                {isCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">
              {isCollapsed ? "展开侧边栏" : "收起侧边栏"}
            </TooltipContent>
          </Tooltip>
        </div>

        {/* New Chat Button */}
        <div className={cn("px-3 pb-4", isCollapsed && "px-2")}>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                onClick={handleCreateSession}
                disabled={createMutation.isPending}
                variant={isCollapsed ? "outline" : "default"}
                size={isCollapsed ? "icon" : "default"}
                className={cn(
                  "w-full shadow-sm transition-all hover:shadow-md",
                  isCollapsed ? "h-10 w-10 p-0 rounded-full" : "justify-start gap-2"
                )}
              >
                {createMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <MessageSquarePlus className="h-4 w-4" />
                )}
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
                  <div key={groupName} className={cn(isCollapsed && "flex flex-col items-center")}>
                    {!isCollapsed && (
                      <h3 className="mb-2 px-2 text-xs font-medium text-muted-foreground/70">
                        {groupName}
                      </h3>
                    )}
                    {isCollapsed && (
                       <div className="mb-2 h-px w-8 bg-border/50" />
                    )}
                    <div className={cn("space-y-0.5", isCollapsed && "space-y-2")}>
                      {groupSessions.map((session) => (
                        <SessionItem
                          key={session.id}
                          session={session}
                          isActive={session.id === sessionId}
                          isCollapsed={isCollapsed}
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
}: Readonly<{
  session: Session
  isActive: boolean
  isCollapsed: boolean
}>): React.JSX.Element {
  const [isHovered, setIsHovered] = useState(false)
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const handleDelete = async (e: React.MouseEvent): Promise<void> => {
    e.preventDefault()
    e.stopPropagation()
    
    if (confirm('确定要删除这个对话吗？')) {
      try {
        await sessionApi.delete(session.id)
        // 刷新会话列表
        void queryClient.invalidateQueries({ queryKey: ['sessions'] })
        toast({
          title: '删除成功',
          description: '会话已删除',
        })
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
        isCollapsed 
          ? 'h-10 w-10 justify-center rounded-full' 
          : 'gap-2 rounded-md px-2 py-2.5',
        isActive
          ? 'bg-secondary text-foreground shadow-sm'
          : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground'
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {isCollapsed ? (
        <MessageCircle className="h-5 w-5" />
      ) : (
        <>
          <div className="flex-1 overflow-hidden">
            <p className="truncate font-medium leading-none">
              {session.title ?? '新对话'}
            </p>
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
        <TooltipTrigger asChild>
          {ItemContent}
        </TooltipTrigger>
        <TooltipContent side="right" className="max-w-[200px] truncate">
          {session.title ?? '新对话'}
        </TooltipContent>
      </Tooltip>
    )
  }

  return ItemContent
}
