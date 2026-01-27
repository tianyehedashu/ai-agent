import { useQuery } from '@tanstack/react-query'
import { Moon, Sun, User } from 'lucide-react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'

import { sessionApi } from '@/api/session'
import { useTheme } from '@/components/theme-provider'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useUserStore } from '@/stores/user'

const pageTitles: Partial<Record<string, string>> = {
  '/': '对话',
  '/chat': '对话',
  '/agents': 'Agents 管理',
  '/studio': '工作台',
  '/settings': '设置',
}

export default function Header(): React.JSX.Element {
  const location = useLocation()
  const navigate = useNavigate()
  const { sessionId } = useParams<{ sessionId?: string }>()
  const { theme, setTheme } = useTheme()
  // 用户信息已由 AuthProvider 在应用启动时获取
  const { currentUser, logout } = useUserStore()

  // 如果有 sessionId，获取会话信息以显示标题
  const { data: session } = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => (sessionId ? sessionApi.get(sessionId) : null),
    enabled: !!sessionId && location.pathname.startsWith('/chat'),
  })

  // 优先显示会话标题，否则显示页面标题
  const title = session?.title ?? pageTitles[location.pathname] ?? '对话'

  const handleLogout = async (): Promise<void> => {
    await logout()
  }

  // 显示用户信息
  const displayName = currentUser?.name ?? '用户'
  const displayEmail = currentUser?.email ?? 'user@example.com'
  const isAnonymous = currentUser?.is_anonymous ?? false

  return (
    <header className="sticky top-0 z-50 flex h-14 items-center justify-between border-b border-border/40 bg-background/95 px-6 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      {/* Page Title */}
      <h1 className="text-lg font-semibold">{title}</h1>

      {/* Actions */}
      <div className="flex items-center gap-2">
        {/* Theme Toggle */}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => {
            setTheme(theme === 'dark' ? 'light' : 'dark')
          }}
        >
          {theme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </Button>

        {/* User Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="relative h-8 w-8 rounded-full">
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
                {isAnonymous && <p className="text-xs italic text-muted-foreground">匿名用户</p>}
              </div>
            </div>
            <DropdownMenuSeparator />
            {isAnonymous && (
              <>
                <DropdownMenuItem
                  onClick={() => {
                    navigate('/login')
                  }}
                >
                  <span className="font-semibold text-primary">登录账号</span>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
              </>
            )}
            <DropdownMenuItem>个人资料</DropdownMenuItem>
            <DropdownMenuItem>API 密钥</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="text-destructive" onClick={handleLogout}>
              退出登录
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
