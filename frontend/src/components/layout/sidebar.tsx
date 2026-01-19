import { useState, useMemo } from 'react'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
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
} from 'lucide-react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

import { sessionApi } from '@/api/session'
import { EditTitleDialog } from '@/components/chat/edit-title-dialog'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
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
import { cn } from '@/lib/utils'
import { useSidebarStore } from '@/stores/sidebar'
import type { Session } from '@/types'

const navigation = [
  { name: 'Agents', href: '/agents', icon: Bot },
  { name: '工作台', href: '/studio', icon: Workflow },
  { name: '设置', href: '/settings', icon: Settings },
]

// Group sessions by date
const groupSessions = (sessions: Session[]) => {
  const groups: Record<string, Session[]> = {
    今天: [],
    昨天: [],
    过去7天: [],
    更早: [],
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

export default function Sidebar(): React.JSX.Element {
  const location = useLocation()
  const navigate = useNavigate()
  const { sessionId } = useParams<{ sessionId?: string }>()
  const { isCollapsed, toggle } = useSidebarStore()
  const [isHistoryOpen, setIsHistoryOpen] = useState(true)
  const queryClient = useQueryClient()
  const { toast } = useToast()

  // Fetch sessions
  const { data: sessionsData, isLoading: isLoadingSessions } = useQuery({
    queryKey: ['sessions'],
    queryFn: () => sessionApi.list(1, 50),
  })

  // Create session mutation
  const createMutation = useMutation({
    mutationFn: (options?: { agentId?: string; title?: string }) =>
      sessionApi.create(options),
    onSuccess: (newSession) => {
      void queryClient.invalidateQueries({ queryKey: ['sessions'] })
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

  const isChatActive =
    location.pathname === '/' ||
    location.pathname === '/chat' ||
    location.pathname.startsWith('/chat/')

  return (
    <TooltipProvider delayDuration={0}>
      <div
        className={cn(
          'relative flex h-full flex-col border-r border-border/50 bg-card/50 backdrop-blur-xl transition-all duration-300',
          isCollapsed ? 'w-16' : 'w-72'
        )}
      >
        {/* Logo */}
        <div className="flex h-14 items-center border-b border-border/50 px-4">
          {!isCollapsed && (
            <Link to="/" className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary shadow-sm">
                <Bot className="h-5 w-5 text-primary-foreground" />
              </div>
              <span className="text-lg font-semibold tracking-tight">AI Agent</span>
            </Link>
          )}
          {isCollapsed && (
            <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-lg bg-primary shadow-sm">
              <Bot className="h-5 w-5 text-primary-foreground" />
            </div>
          )}
        </div>

        {/* New Chat Button */}
        <div className="p-3">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="default"
                className={cn(
                  'w-full shadow-sm transition-all hover:shadow-md',
                  isCollapsed ? 'px-0' : 'justify-start gap-2'
                )}
                onClick={handleCreateSession}
                disabled={createMutation.isPending}
              >
                {createMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="h-4 w-4" />
                )}
                {!isCollapsed && <span>新建对话</span>}
              </Button>
            </TooltipTrigger>
            {isCollapsed && <TooltipContent side="right">新建对话</TooltipContent>}
          </Tooltip>
        </div>

        <ScrollArea className="flex-1 px-3">
          {/* Chat History Section */}
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
                  <span className="flex-1 text-left">对话</span>
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
                  <p className="px-3 py-2 text-xs text-muted-foreground">暂无对话记录</p>
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
              <TooltipContent side="right">对话</TooltipContent>
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
}: Readonly<{
  session: Session
  isActive: boolean
}>): React.JSX.Element {
  const [isHovered, setIsHovered] = useState(false)
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const handleDelete = async (e: React.MouseEvent): Promise<void> => {
    e.preventDefault()
    e.stopPropagation()

    if (confirm('确定要删除这个对话吗？')) {
      try {
        await sessionApi.delete(session.id)
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

  return (
    <Link
      to={`/chat/${session.id}`}
      className={cn(
        'group flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-all duration-150',
        isActive
          ? 'bg-secondary text-foreground'
          : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground'
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <span className="flex-1 truncate text-[13px]">{session.title ?? '新对话'}</span>
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
        }}
      />
    </Link>
  )
}
