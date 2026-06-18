import { useQuery } from '@tanstack/react-query'
import { Moon, Sun, User } from 'lucide-react'
import { useLocation, useParams } from 'react-router-dom'

import { sessionApi } from '@/api/session'
import { useTheme } from '@/components/theme-provider'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useCurrentUser, useUserStore } from '@/stores/user'

const pageTitles: Partial<Record<string, string>> = {
  '/': '对话',
  '/chat': '对话',
  '/agents': 'Agents 管理',
  '/mcp': 'MCP 服务器',
  '/mcp/system': '系统 MCP',
  '/video-tasks': '视频任务',
  '/video-tasks/history': '历史任务',
  '/settings': '设置',
}

function resolveSectionLabel(pathname: string): string {
  if (pathname.startsWith('/gateway')) return 'AI 基础设施'
  if (pathname.startsWith('/video-tasks') || pathname.startsWith('/listing-studio'))
    return '创作工作台'
  if (pathname.startsWith('/admin') || pathname.startsWith('/mcp')) return '平台管理'
  if (pathname.startsWith('/settings')) return '系统设置'
  return 'AI Workspace'
}

export default function Header(): React.JSX.Element {
  const location = useLocation()
  const { sessionId } = useParams<{ sessionId?: string }>()
  const { theme, setTheme } = useTheme()
  // 用户信息已由 AuthProvider 在应用启动时获取
  const currentUser = useCurrentUser()
  const isAuthenticated = currentUser !== null
  const { logout } = useUserStore()
  const { isPlatformAdmin, isPlatformViewer } = useGatewayPermission()

  // 如果有 sessionId，获取会话信息以显示标题
  const { data: session } = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => (sessionId ? sessionApi.get(sessionId) : null),
    enabled: isAuthenticated && !!sessionId && location.pathname.startsWith('/chat'),
  })

  // 优先显示会话标题，否则显示页面标题
  const title = session?.title ?? pageTitles[location.pathname] ?? '对话'
  const sectionLabel = resolveSectionLabel(location.pathname)

  const handleLogout = async (): Promise<void> => {
    await logout()
  }

  // 显示用户信息
  const displayName = currentUser?.name ?? '用户'
  const displayEmail = currentUser?.email ?? 'user@example.com'

  return (
    <header className="sticky top-0 z-[60] flex h-14 items-center justify-between border-b border-border/60 bg-card/80 px-6 shadow-sm shadow-black/[0.02] backdrop-blur-xl supports-[backdrop-filter]:bg-card/65 dark:shadow-black/20">
      {/* Page Title */}
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-primary shadow-[0_0_14px_hsl(var(--primary)/0.7)]" />
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            {sectionLabel}
          </p>
        </div>
        <h1 className="truncate text-base font-semibold tracking-tight">{title}</h1>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        {/* Theme Toggle */}
        <Button
          variant="ghost"
          size="icon"
          aria-label={theme === 'dark' ? '切换到浅色主题' : '切换到深色主题'}
          onClick={() => {
            setTheme(theme === 'dark' ? 'light' : 'dark')
          }}
        >
          {theme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </Button>

        {/* User Menu */}
        <div className="flex items-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className="relative h-8 w-8 rounded-full"
                aria-label="打开用户菜单"
              >
                <Avatar className="h-8 w-8">
                  <AvatarImage src="" alt="用户头像" />
                  <AvatarFallback>
                    <User className="h-4 w-4" />
                  </AvatarFallback>
                </Avatar>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <div className="flex items-center justify-start gap-2 p-2">
                <div className="flex flex-col space-y-1 leading-none">
                  <p className="font-medium">{displayName}</p>
                  <p className="text-xs text-muted-foreground">{displayEmail}</p>
                  {isPlatformAdmin && (
                    <Badge variant="secondary" className="w-fit text-xs font-normal">
                      平台管理员
                    </Badge>
                  )}
                  {isPlatformViewer && <p className="text-xs text-muted-foreground">只读账号</p>}
                </div>
              </div>
              <DropdownMenuSeparator />
              <DropdownMenuItem>个人资料</DropdownMenuItem>
              <DropdownMenuItem>API 密钥</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-destructive"
                onSelect={(event) => {
                  event.preventDefault()
                  void handleLogout()
                }}
              >
                退出登录
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  )
}
