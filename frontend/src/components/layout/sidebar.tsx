import { MessageSquare, Bot, Workflow, Settings, Plus, ChevronLeft } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import { useSidebarStore } from '@/stores/sidebar'

const navigation = [
  { name: '对话', href: '/', icon: MessageSquare },
  { name: 'Agents', href: '/agents', icon: Bot },
  { name: '工作台', href: '/studio', icon: Workflow },
  { name: '设置', href: '/settings', icon: Settings },
]

export default function Sidebar(): React.JSX.Element {
  const location = useLocation()
  const { isCollapsed, toggle } = useSidebarStore()

  return (
    <div
      className={cn(
        'relative flex h-full flex-col border-r bg-card transition-all duration-300',
        isCollapsed ? 'w-16' : 'w-64'
      )}
    >
      {/* Logo */}
      <div className="flex h-14 items-center border-b px-4">
        {!isCollapsed && (
          <Link to="/" className="flex items-center gap-2">
            <Bot className="h-6 w-6 text-primary" />
            <span className="text-lg font-semibold">AI Agent</span>
          </Link>
        )}
        {isCollapsed && <Bot className="mx-auto h-6 w-6 text-primary" />}
      </div>

      {/* New Chat Button */}
      <div className="p-3">
        <Button variant="default" className={cn('w-full', isCollapsed && 'px-2')} asChild>
          <Link to="/chat">
            <Plus className="h-4 w-4" />
            {!isCollapsed && <span className="ml-2">新对话</span>}
          </Link>
        </Button>
      </div>

      {/* Navigation */}
      <ScrollArea className="flex-1 px-3">
        <nav className="space-y-1">
          {navigation.map((item) => {
            const isActive =
              location.pathname === item.href ||
              (item.href !== '/' && location.pathname.startsWith(item.href))

            return (
              <Link
                key={item.name}
                to={item.href}
                className={cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                  isCollapsed && 'justify-center'
                )}
              >
                <item.icon className="h-4 w-4 flex-shrink-0" />
                {!isCollapsed && <span>{item.name}</span>}
              </Link>
            )
          })}
        </nav>
      </ScrollArea>

      {/* Collapse Button */}
      <Button
        variant="ghost"
        size="icon"
        className="absolute -right-3 top-6 h-6 w-6 rounded-full border bg-background"
        onClick={toggle}
      >
        <ChevronLeft className={cn('h-4 w-4 transition-transform', isCollapsed && 'rotate-180')} />
      </Button>
    </div>
  )
}
