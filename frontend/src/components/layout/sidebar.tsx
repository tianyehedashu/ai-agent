import { useState, useMemo } from 'react'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  MessageSquare,
  Bot,
  Workflow,
  Settings,
  Plus,
  ChevronLeft,
  ChevronDown,
  ChevronRight,
  Trash2,
  MoreVertical,
  Loader2,
  Pencil,
  Zap,
  Server,
  Video,
  Package,
} from 'lucide-react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

import { sessionApi } from '@/api/session'
import { EditTitleDialog } from '@/components/chat/edit-title-dialog'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { useToast } from '@/hooks/use-toast'
import { groupSessionsByDate } from '@/lib/session-utils'
import { cn } from '@/lib/utils'
import { useChatStore } from '@/stores/chat'
import { useSidebarStore } from '@/stores/sidebar'
import type { Session } from '@/types'
import { isVideoSession } from '@/types'

const navigation = [
  { name: 'Agents', href: '/agents', icon: Bot },
  { name: 'MCP 服务器', href: '/mcp', icon: Zap },
  { name: '系统 MCP', href: '/mcp/system', icon: Server },
  { name: '视频', href: '/video-tasks', icon: Video },
  { name: '产品信息', href: '/product-info', icon: Package },
  { name: '工作台', href: '/studio', icon: Workflow },
  { name: '设置', href: '/settings', icon: Settings },
]

export default function Sidebar(): React.JSX.Element {
  const location = useLocation()
  const navigate = useNavigate()
  const { sessionId } = useParams<{ sessionId?: string }>()
  const { isCollapsed, toggle } = useSidebarStore()
  const [isHistoryOpen, setIsHistoryOpen] = useState(true)

  // Fetch sessions
  const { data: sessionsData, isLoading: isLoadingSessions } = useQuery({
    queryKey: ['sessions'],
    queryFn: () => sessionApi.list(1, 50),
  })

  const sessions = useMemo(() => sessionsData?.items ?? [], [sessionsData?.items])
  const groupedSessions = useMemo(() => groupSessionsByDate(sessions), [sessions])

  // 判断当前是否在聊天页面（会话区域高亮用）
  const isChatActive =
    location.pathname === '/' ||
    location.pathname === '/chat' ||
    location.pathname.startsWith('/chat/')

  // 当前会话（用于侧栏显示当前会话标题，仅聊天页面）
  const { data: currentSession } = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => (sessionId ? sessionApi.get(sessionId) : Promise.resolve(null)),
    enabled: !!sessionId && isChatActive,
  })

  const handleCreateChat = (): void => {
    navigate('/chat')
  }

  return (
    <TooltipProvider delayDuration={0}>
      <div
        className={cn(
          'relative flex h-full flex-col border-r border-border/40 bg-background/95 backdrop-blur transition-all duration-300 supports-[backdrop-filter]:bg-background/60',
          isCollapsed ? 'w-16' : 'w-72'
        )}
      >
        {/* Logo */}
        <div className="flex h-14 items-center border-b border-border/40 px-4">
          {!isCollapsed && (
            <Link to="/" className="group flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 shadow-sm transition-colors group-hover:bg-primary/20">
                <Bot className="h-5 w-5 text-primary" />
              </div>
              <span className="text-lg font-semibold tracking-tight">AI Agent</span>
            </Link>
          )}
          {isCollapsed && (
            <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 shadow-sm">
              <Bot className="h-5 w-5 text-primary" />
            </div>
          )}
        </div>

        {/* 新建：直接进入新建对话，不再弹出「对话/视频」选项 */}
        <div className="p-3">
          {isCollapsed ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="default"
                  className="w-full bg-primary px-0 text-primary-foreground shadow-sm transition-all hover:bg-primary/90 hover:shadow-md"
                  onClick={handleCreateChat}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">新建对话</TooltipContent>
            </Tooltip>
          ) : (
            <Button
              variant="default"
              className="w-full justify-start gap-2 bg-primary text-primary-foreground shadow-sm transition-all hover:bg-primary/90 hover:shadow-md"
              onClick={handleCreateChat}
            >
              <Plus className="h-4 w-4" />
              <span>新建对话</span>
            </Button>
          )}
        </div>

        <ScrollArea className="flex-1 px-3">
          {/* Session History Section */}
          {!isCollapsed ? (
            <Collapsible open={isHistoryOpen} onOpenChange={setIsHistoryOpen}>
              <CollapsibleTrigger asChild>
                <button
                  className={cn(
                    'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors',
                    isChatActive
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                  )}
                >
                  <MessageSquare className="h-4 w-4 flex-shrink-0" />
                  <span className="flex-1 truncate text-left">
                    {isChatActive && currentSession?.title ? currentSession.title : '会话'}
                  </span>
                  {isHistoryOpen ? (
                    <ChevronDown className="h-3 w-3 opacity-50" />
                  ) : (
                    <ChevronRight className="h-3 w-3 opacity-50" />
                  )}
                </button>
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-1">
                {isLoadingSessions ? (
                  <div className="flex justify-center py-4">
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                  </div>
                ) : sessions.length === 0 ? (
                  <p className="px-3 py-2 text-xs text-muted-foreground">暂无会话记录</p>
                ) : (
                  <div className="space-y-3 pb-2">
                    {Object.entries(groupedSessions).map(([groupName, groupSessions]) => {
                      if (groupSessions.length === 0) return null
                      return (
                        <div key={groupName}>
                          <p className="mb-1 px-3 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/60">
                            {groupName}
                          </p>
                          <div className="space-y-0.5">
                            {groupSessions.map((session) => (
                              <SessionItem
                                key={session.id}
                                session={session}
                                isActive={session.id === sessionId}
                                currentSessionId={sessionId}
                              />
                            ))}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </CollapsibleContent>
            </Collapsible>
          ) : (
            <Tooltip>
              <TooltipTrigger asChild>
                <Link
                  to="/chat"
                  className={cn(
                    'flex items-center justify-center rounded-lg p-2 transition-colors',
                    isChatActive
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                  )}
                >
                  <MessageSquare className="h-4 w-4" />
                </Link>
              </TooltipTrigger>
              <TooltipContent side="right">会话</TooltipContent>
            </Tooltip>
          )}

          {/* Separator */}
          <div className="my-3 h-px bg-border/50" />

          {/* Other Navigation */}
          <nav className="space-y-1">
            {navigation.map((item) => {
              const isActive =
                location.pathname === item.href ||
                (item.href !== '/' && location.pathname.startsWith(item.href))

              return isCollapsed ? (
                <Tooltip key={item.name}>
                  <TooltipTrigger asChild>
                    <Link
                      to={item.href}
                      className={cn(
                        'flex items-center justify-center rounded-lg p-2 transition-colors',
                        isActive
                          ? 'bg-primary/10 text-primary'
                          : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                      )}
                    >
                      <item.icon className="h-4 w-4" />
                    </Link>
                  </TooltipTrigger>
                  <TooltipContent side="right">{item.name}</TooltipContent>
                </Tooltip>
              ) : (
                <Link
                  key={item.name}
                  to={item.href}
                  className={cn(
                    'flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors',
                    isActive
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                  )}
                >
                  <item.icon className="h-4 w-4 flex-shrink-0" />
                  <span>{item.name}</span>
                </Link>
              )
            })}
          </nav>
        </ScrollArea>

        {/* Collapse Button */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="absolute -right-3 top-6 z-10 h-6 w-6 rounded-full border bg-background shadow-sm"
              onClick={toggle}
            >
              <ChevronLeft
                className={cn('h-3 w-3 transition-transform', isCollapsed && 'rotate-180')}
              />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right">{isCollapsed ? '展开' : '收起'}</TooltipContent>
        </Tooltip>
      </div>
    </TooltipProvider>
  )
}

function SessionItem({
  session,
  isActive,
  currentSessionId,
}: Readonly<{
  session: Session
  isActive: boolean
  currentSessionId?: string
}>): React.JSX.Element {
  const [isHovered, setIsHovered] = useState(false)
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { toast } = useToast()

  // 判断会话类型（路由与图标）
  const isVideo = isVideoSession(session)
  const Icon = isVideo ? Video : MessageSquare
  const href = isVideo ? `/video-tasks/${session.id}` : `/chat/${session.id}`
  // 无标题时兜底：有视频任务的会话显示「新视频」，否则「新对话」
  const defaultTitle = (session.videoTaskCount ?? 0) > 0 ? '新视频' : '新对话'

  const handleDelete = async (e: React.MouseEvent): Promise<void> => {
    e.preventDefault()
    e.stopPropagation()

    if (confirm('确定要删除这个会话吗？')) {
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
          navigate(isVideo ? '/video-tasks' : '/chat')
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

  return (
    <Link
      to={href}
      className={cn(
        'group flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-all duration-150',
        isActive
          ? 'bg-secondary text-foreground'
          : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground'
      )}
      onMouseEnter={() => {
        setIsHovered(true)
      }}
      onMouseLeave={() => {
        setIsHovered(false)
      }}
    >
      <Icon className={cn('h-3.5 w-3.5 flex-shrink-0', isVideo && 'text-purple-500')} />
      <span className="flex-1 truncate text-[13px]">{session.title ?? defaultTitle}</span>
      {(isHovered || isActive) && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-5 w-5 shrink-0 opacity-0 transition-opacity group-hover:opacity-100 data-[state=open]:opacity-100"
              onClick={(e) => {
                e.preventDefault()
              }}
            >
              <MoreVertical className="h-3 w-3" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-40">
            <DropdownMenuItem
              onClick={(e) => {
                e.preventDefault()
                setIsEditDialogOpen(true)
              }}
            >
              <Pencil className="mr-2 h-3.5 w-3.5" />
              编辑标题
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="text-destructive focus:text-destructive"
              onClick={handleDelete}
            >
              <Trash2 className="mr-2 h-3.5 w-3.5" />
              删除
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )}

      <EditTitleDialog
        open={isEditDialogOpen}
        onOpenChange={setIsEditDialogOpen}
        sessionId={session.id}
        currentTitle={session.title}
        onSuccess={() => {
          void queryClient.invalidateQueries({ queryKey: ['sessions'] })
          void queryClient.invalidateQueries({ queryKey: ['session', session.id] })
        }}
      />
    </Link>
  )
}
