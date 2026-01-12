# 🎨 AI Agent Frontend 代码规范

> **版本**: 1.0.0
> **更新日期**: 2026-01-12
> **适用范围**: frontend/ 目录下所有 TypeScript/React 代码

---

## 📋 目录

1. [核心原则](#核心原则)
2. [项目结构](#项目结构)
3. [TypeScript 规范](#typescript-规范)
4. [React 组件规范](#react-组件规范)
5. [状态管理](#状态管理)
6. [样式规范](#样式规范)
7. [API 调用](#api-调用)
8. [错误处理](#错误处理)
9. [性能优化](#性能优化)
10. [测试规范](#测试规范)
11. [质量检测工具](#质量检测工具)
12. [Git 工作流](#git-工作流)

---

## 核心原则

### 1. 类型安全优先 (Type-Safe First)

所有代码必须有完整的 TypeScript 类型，禁止使用 `any`。

```typescript
// ✅ 正确
interface User {
  id: string
  name: string
  email: string
}

function getUser(id: string): Promise<User> {
  // ...
}

// ❌ 错误
function getUser(id: any): any {
  // ...
}
```

### 2. 不重复造轮子 (DRY)

- 使用项目定义的类型 (`@/types`)
- 复用现有工具函数 (`@/lib/utils`)
- 使用 Radix UI + shadcn/ui 组件
- 使用 React Query 处理数据请求

### 3. 单一职责 (SRP)

- 每个组件只做一件事
- 业务逻辑抽离到 hooks
- 样式使用 Tailwind 类名

### 4. 组合优于继承 (Composition over Inheritance)

```tsx
// ✅ 组合模式
<Card>
  <CardHeader>
    <CardTitle>标题</CardTitle>
  </CardHeader>
  <CardContent>内容</CardContent>
</Card>

// ❌ 避免深度嵌套的继承
class MyCard extends Card extends BaseComponent { ... }
```

---

## 项目结构

```
frontend/
├── src/
│   ├── api/                 # API 调用层
│   │   ├── client.ts        # HTTP 客户端
│   │   ├── agent.ts         # Agent API
│   │   ├── chat.ts          # Chat API
│   │   └── session.ts       # Session API
│   │
│   ├── components/          # 组件
│   │   ├── ui/              # 基础 UI 组件 (shadcn/ui)
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   └── input.tsx
│   │   ├── layout/          # 布局组件
│   │   │   ├── header.tsx
│   │   │   └── sidebar.tsx
│   │   └── shared/          # 共享业务组件
│   │
│   ├── hooks/               # 自定义 Hooks
│   │   ├── use-debounce.ts
│   │   └── use-local-storage.ts
│   │
│   ├── lib/                 # 工具函数
│   │   └── utils.ts
│   │
│   ├── pages/               # 页面组件
│   │   ├── chat/
│   │   │   ├── index.tsx
│   │   │   └── components/
│   │   ├── agents/
│   │   └── studio/
│   │
│   ├── stores/              # Zustand 状态存储
│   │   ├── chat.ts
│   │   └── sidebar.ts
│   │
│   ├── types/               # TypeScript 类型定义
│   │   └── index.ts
│   │
│   ├── test/                # 测试配置和工具
│   │   └── setup.ts
│   │
│   ├── App.tsx              # 应用根组件
│   └── main.tsx             # 入口文件
│
├── docs/                    # 文档
├── eslint.config.js         # ESLint 配置
├── .prettierrc              # Prettier 配置
├── tsconfig.json            # TypeScript 配置
├── tailwind.config.js       # Tailwind 配置
└── vite.config.ts           # Vite 配置
```

### 各目录职责

| 目录 | 职责 | 示例 |
|------|------|------|
| `api/` | HTTP 请求封装 | `agentApi.create()` |
| `components/ui/` | 基础 UI 组件 | Button, Card, Input |
| `components/layout/` | 布局组件 | Header, Sidebar |
| `components/shared/` | 共享业务组件 | UserAvatar, AgentCard |
| `hooks/` | 可复用逻辑 | useDebounce, useLocalStorage |
| `lib/` | 工具函数 | cn(), formatDate() |
| `pages/` | 页面组件 | ChatPage, AgentsPage |
| `stores/` | 全局状态 | useChatStore |
| `types/` | 类型定义 | User, Agent, Message |

---

## TypeScript 规范

### 3.1 严格类型配置

```json
// tsconfig.json
{
  "compilerOptions": {
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  }
}
```

### 3.2 类型定义规范

```typescript
// ✅ 使用 interface 定义对象类型
interface User {
  id: string
  name: string
  email: string
  avatar?: string  // 可选属性
}

// ✅ 使用 type 定义联合类型/交叉类型
type MessageRole = 'user' | 'assistant' | 'system' | 'tool'
type UserWithPosts = User & { posts: Post[] }

// ✅ 使用泛型增强复用性
interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: string
}

// ✅ 使用 const 断言
const ROLES = ['admin', 'user', 'guest'] as const
type Role = (typeof ROLES)[number]  // 'admin' | 'user' | 'guest'
```

### 3.3 类型导入规范

```typescript
// ✅ 使用 type-only imports
import { type User, type Agent } from '@/types'
import type { ComponentProps } from 'react'

// ✅ 混合导入时分开
import { useState, useEffect } from 'react'
import type { FC, ReactNode } from 'react'
```

### 3.4 禁止使用 any

```typescript
// ❌ 禁止
function process(data: any): any { ... }

// ✅ 使用 unknown + 类型守卫
function process(data: unknown): User {
  if (!isUser(data)) {
    throw new Error('Invalid data')
  }
  return data
}

function isUser(data: unknown): data is User {
  return (
    typeof data === 'object' &&
    data !== null &&
    'id' in data &&
    'name' in data
  )
}
```

### 3.5 使用项目定义的类型

```typescript
// ✅ 复用 @/types 中的类型
import type { User, Agent, Message, Session } from '@/types'
import type { ChatEvent, ChatEventType } from '@/types'

// ✅ 避免重复定义
// 如果需要扩展，使用交叉类型
type UserWithExtra = User & {
  extraField: string
}
```

---

## React 组件规范

### 4.1 组件定义

```tsx
// ✅ 使用函数组件 + 箭头函数
interface ButtonProps {
  variant?: 'default' | 'destructive' | 'outline'
  size?: 'default' | 'sm' | 'lg'
  children: React.ReactNode
  onClick?: () => void
}

export const Button = ({ variant = 'default', size = 'default', children, onClick }: ButtonProps) => {
  return (
    <button
      className={cn(buttonVariants({ variant, size }))}
      onClick={onClick}
    >
      {children}
    </button>
  )
}

// ✅ 需要 forwardRef 时
export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn('...', className)}
        ref={ref}
        {...props}
      />
    )
  }
)
Input.displayName = 'Input'
```

### 4.2 组件文件结构

```tsx
// 1. 导入 (按顺序)
import { useState, useCallback } from 'react'            // React
import { useQuery } from '@tanstack/react-query'         // 第三方
import { Button } from '@/components/ui/button'          // 内部组件
import { cn } from '@/lib/utils'                         // 工具函数
import type { User } from '@/types'                      // 类型

// 2. 类型定义
interface UserCardProps {
  user: User
  onSelect?: (user: User) => void
}

// 3. 组件定义
export const UserCard = ({ user, onSelect }: UserCardProps) => {
  // 3.1 Hooks
  const [isHovered, setIsHovered] = useState(false)

  // 3.2 Callbacks
  const handleClick = useCallback(() => {
    onSelect?.(user)
  }, [user, onSelect])

  // 3.3 Render
  return (
    <div
      className={cn('p-4 rounded-lg', isHovered && 'bg-accent')}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={handleClick}
    >
      <h3>{user.name}</h3>
      <p>{user.email}</p>
    </div>
  )
}
```

### 4.3 Props 规范

```tsx
// ✅ 使用解构 + 默认值
interface CardProps {
  title: string
  description?: string
  variant?: 'default' | 'bordered'
  className?: string
  children?: React.ReactNode
}

export const Card = ({
  title,
  description,
  variant = 'default',
  className,
  children,
}: CardProps) => {
  // ...
}

// ✅ 透传 HTML 属性
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'destructive'
}

export const Button = ({ variant, className, ...props }: ButtonProps) => {
  return <button className={cn(styles, className)} {...props} />
}
```

### 4.4 条件渲染

```tsx
// ✅ 简单条件用 &&
{isLoading && <Spinner />}

// ✅ 二选一用三元
{isLoading ? <Spinner /> : <Content />}

// ✅ 多条件用早返回
if (isLoading) return <Spinner />
if (error) return <ErrorMessage error={error} />
if (!data) return <Empty />
return <Content data={data} />

// ✅ 复杂条件抽成变量
const showSidebar = isDesktop && !isCollapsed
{showSidebar && <Sidebar />}
```

### 4.5 列表渲染

```tsx
// ✅ 使用唯一且稳定的 key
{users.map((user) => (
  <UserCard key={user.id} user={user} />
))}

// ❌ 避免使用 index 作为 key (除非列表是静态的)
{items.map((item, index) => (
  <Item key={index} item={item} />  // 不推荐
))}
```

---

## 状态管理

### 5.1 Zustand Store 规范

```typescript
// stores/chat.ts
import { create } from 'zustand'
import type { Message, Session } from '@/types'

// 1. 定义状态接口
interface ChatState {
  // 状态
  currentSession: Session | null
  messages: Message[]
  isLoading: boolean

  // Actions
  setCurrentSession: (session: Session | null) => void
  addMessage: (message: Message) => void
  clearMessages: () => void
  setIsLoading: (loading: boolean) => void
}

// 2. 创建 Store
export const useChatStore = create<ChatState>((set) => ({
  // 初始状态
  currentSession: null,
  messages: [],
  isLoading: false,

  // Actions
  setCurrentSession: (session) => set({ currentSession: session }),
  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),
  clearMessages: () => set({ messages: [] }),
  setIsLoading: (loading) => set({ isLoading: loading }),
}))
```

### 5.2 选择性订阅

```tsx
// ✅ 只订阅需要的状态，避免不必要的重渲染
const messages = useChatStore((state) => state.messages)
const addMessage = useChatStore((state) => state.addMessage)

// ❌ 避免订阅整个 store
const store = useChatStore()  // 任何变化都会导致重渲染
```

### 5.3 React Query 数据获取

```typescript
// hooks/use-agents.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { agentApi } from '@/api/agent'
import type { Agent, AgentCreateInput } from '@/types'

// 查询 Key 常量
export const agentKeys = {
  all: ['agents'] as const,
  lists: () => [...agentKeys.all, 'list'] as const,
  list: (filters: string) => [...agentKeys.lists(), { filters }] as const,
  details: () => [...agentKeys.all, 'detail'] as const,
  detail: (id: string) => [...agentKeys.details(), id] as const,
}

// 获取列表
export function useAgents() {
  return useQuery({
    queryKey: agentKeys.lists(),
    queryFn: () => agentApi.list(),
  })
}

// 获取详情
export function useAgent(id: string) {
  return useQuery({
    queryKey: agentKeys.detail(id),
    queryFn: () => agentApi.get(id),
    enabled: !!id,
  })
}

// 创建
export function useCreateAgent() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: AgentCreateInput) => agentApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: agentKeys.lists() })
    },
  })
}
```

---

## 样式规范

### 6.1 Tailwind CSS 使用

```tsx
// ✅ 使用 cn() 合并类名
import { cn } from '@/lib/utils'

<div className={cn(
  'p-4 rounded-lg',           // 基础样式
  'bg-card text-card-foreground',  // 主题颜色
  isActive && 'border-primary',    // 条件样式
  className                         // 外部传入
)} />

// ✅ 使用语义化的主题变量
'bg-background'    // 而不是 'bg-white' 或 'bg-gray-900'
'text-foreground'  // 而不是 'text-black'
'bg-primary'       // 而不是 'bg-blue-500'
```

### 6.2 CSS 变量主题

```css
/* index.css */
@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --primary: 222.2 47.4% 11.2%;
    --primary-foreground: 210 40% 98%;
    /* ... */
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    /* ... */
  }
}
```

### 6.3 CVA 变体模式

```tsx
// components/ui/button.tsx
import { cva, type VariantProps } from 'class-variance-authority'

const buttonVariants = cva(
  // 基础样式
  'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90',
        destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
        outline: 'border border-input bg-background hover:bg-accent',
        ghost: 'hover:bg-accent hover:text-accent-foreground',
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-9 px-3',
        lg: 'h-11 px-8',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = ({ className, variant, size, ...props }: ButtonProps) => {
  return (
    <button
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}
```

### 6.4 响应式设计

```tsx
// ✅ 移动优先
<div className="
  flex flex-col        // 移动端：垂直排列
  md:flex-row          // 平板及以上：水平排列
  lg:gap-8             // 大屏幕：更大间距
">
  <aside className="
    w-full             // 移动端：全宽
    md:w-64            // 平板及以上：固定宽度
    lg:w-80            // 大屏幕：更宽
  ">
    <Sidebar />
  </aside>
  <main className="flex-1">
    <Content />
  </main>
</div>
```

---

## API 调用

### 7.1 API 客户端

```typescript
// api/client.ts
class ApiClient {
  private baseUrl: string
  private token: string | null = null

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
    this.token = localStorage.getItem('auth_token')
  }

  // 通用请求方法
  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...(this.token && { Authorization: `Bearer ${this.token}` }),
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers: { ...headers, ...options.headers },
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
  }

  // 便捷方法
  async get<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: 'GET' })
  }

  async post<T>(path: string, data?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    })
  }
}

export const apiClient = new ApiClient(import.meta.env.VITE_API_URL || '')
```

### 7.2 API 模块

```typescript
// api/agent.ts
import { apiClient } from './client'
import type { Agent, AgentCreateInput } from '@/types'

export const agentApi = {
  list: () => apiClient.get<Agent[]>('/api/v1/agents'),

  get: (id: string) => apiClient.get<Agent>(`/api/v1/agents/${id}`),

  create: (data: AgentCreateInput) =>
    apiClient.post<Agent>('/api/v1/agents', data),

  update: (id: string, data: Partial<AgentCreateInput>) =>
    apiClient.put<Agent>(`/api/v1/agents/${id}`, data),

  delete: (id: string) => apiClient.delete(`/api/v1/agents/${id}`),
}
```

---

## 错误处理

### 8.1 API 错误处理

```tsx
// 使用 React Query 的错误处理
function AgentList() {
  const { data, error, isLoading } = useAgents()

  if (isLoading) return <Spinner />

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>加载失败</AlertTitle>
        <AlertDescription>{error.message}</AlertDescription>
      </Alert>
    )
  }

  return <AgentGrid agents={data ?? []} />
}
```

### 8.2 Error Boundary

```tsx
// components/error-boundary.tsx
import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error?: Error
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div className="p-8 text-center">
          <h2 className="text-lg font-semibold">出错了</h2>
          <p className="text-muted-foreground">{this.state.error?.message}</p>
        </div>
      )
    }

    return this.props.children
  }
}
```

### 8.3 表单验证

```tsx
// 使用 Zod + React Hook Form
import { z } from 'zod'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'

const agentSchema = z.object({
  name: z.string().min(1, '名称不能为空').max(50, '名称最多50个字符'),
  description: z.string().optional(),
  model: z.string().min(1, '请选择模型'),
  temperature: z.number().min(0).max(2),
})

type AgentFormData = z.infer<typeof agentSchema>

function AgentForm({ onSubmit }: { onSubmit: (data: AgentFormData) => void }) {
  const form = useForm<AgentFormData>({
    resolver: zodResolver(agentSchema),
    defaultValues: {
      name: '',
      temperature: 0.7,
    },
  })

  return (
    <form onSubmit={form.handleSubmit(onSubmit)}>
      <Input {...form.register('name')} />
      {form.formState.errors.name && (
        <p className="text-destructive text-sm">
          {form.formState.errors.name.message}
        </p>
      )}
      {/* ... */}
    </form>
  )
}
```

---

## 性能优化

### 9.1 Memo 使用

```tsx
import { memo, useMemo, useCallback } from 'react'

// ✅ 对于接收复杂 props 的组件使用 memo
const MessageItem = memo(({ message }: { message: Message }) => {
  return (
    <div className="p-4">
      <p>{message.content}</p>
    </div>
  )
})

// ✅ 使用 useMemo 缓存计算结果
const filteredMessages = useMemo(
  () => messages.filter((m) => m.role !== 'system'),
  [messages]
)

// ✅ 使用 useCallback 缓存回调函数
const handleClick = useCallback((id: string) => {
  selectItem(id)
}, [selectItem])
```

### 9.2 懒加载

```tsx
import { lazy, Suspense } from 'react'

// 懒加载页面组件
const ChatPage = lazy(() => import('@/pages/chat'))
const AgentsPage = lazy(() => import('@/pages/agents'))
const StudioPage = lazy(() => import('@/pages/studio'))

// 使用时包裹 Suspense
<Suspense fallback={<PageSkeleton />}>
  <Routes>
    <Route path="/chat" element={<ChatPage />} />
    <Route path="/agents" element={<AgentsPage />} />
    <Route path="/studio" element={<StudioPage />} />
  </Routes>
</Suspense>
```

### 9.3 虚拟列表

```tsx
// 对于长列表使用虚拟化
import { useVirtualizer } from '@tanstack/react-virtual'

function MessageList({ messages }: { messages: Message[] }) {
  const parentRef = useRef<HTMLDivElement>(null)

  const virtualizer = useVirtualizer({
    count: messages.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 80,
    overscan: 5,
  })

  return (
    <div ref={parentRef} className="h-full overflow-auto">
      <div
        style={{ height: `${virtualizer.getTotalSize()}px`, position: 'relative' }}
      >
        {virtualizer.getVirtualItems().map((virtualRow) => (
          <div
            key={virtualRow.index}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              transform: `translateY(${virtualRow.start}px)`,
            }}
          >
            <MessageItem message={messages[virtualRow.index]} />
          </div>
        ))}
      </div>
    </div>
  )
}
```

---

## 测试规范

### 10.1 测试文件结构

```
src/
├── components/
│   └── ui/
│       ├── button.tsx
│       └── button.test.tsx    # 组件测试放在同目录
├── hooks/
│   ├── use-debounce.ts
│   └── use-debounce.test.ts   # Hook 测试
└── lib/
    ├── utils.ts
    └── utils.test.ts          # 工具函数测试
```

### 10.2 组件测试

```tsx
// components/ui/button.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { Button } from './button'

describe('Button', () => {
  it('renders children correctly', () => {
    render(<Button>Click me</Button>)
    expect(screen.getByText('Click me')).toBeInTheDocument()
  })

  it('calls onClick when clicked', () => {
    const handleClick = vi.fn()
    render(<Button onClick={handleClick}>Click me</Button>)

    fireEvent.click(screen.getByText('Click me'))
    expect(handleClick).toHaveBeenCalledTimes(1)
  })

  it('applies variant styles correctly', () => {
    render(<Button variant="destructive">Delete</Button>)
    const button = screen.getByText('Delete')
    expect(button).toHaveClass('bg-destructive')
  })

  it('is disabled when disabled prop is true', () => {
    render(<Button disabled>Disabled</Button>)
    expect(screen.getByText('Disabled')).toBeDisabled()
  })
})
```

### 10.3 Hook 测试

```tsx
// hooks/use-debounce.test.ts
import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { useDebounce } from './use-debounce'

describe('useDebounce', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns initial value immediately', () => {
    const { result } = renderHook(() => useDebounce('test', 500))
    expect(result.current).toBe('test')
  })

  it('debounces value changes', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 500),
      { initialProps: { value: 'initial' } }
    )

    rerender({ value: 'updated' })
    expect(result.current).toBe('initial')

    act(() => {
      vi.advanceTimersByTime(500)
    })

    expect(result.current).toBe('updated')
  })
})
```

### 10.4 运行测试

```bash
# 运行所有测试
npm test

# 交互式 UI
npm run test:ui

# 单次运行
npm run test:run

# 带覆盖率
npm run test:coverage
```

---

## 质量检测工具

### 11.1 工具链

| 工具 | 用途 | 命令 |
|------|------|------|
| TypeScript | 类型检查 | `npm run typecheck` |
| ESLint | 代码检查 | `npm run lint` |
| Prettier | 代码格式化 | `npm run format` |
| Vitest | 单元测试 | `npm test` |
| Husky | Git hooks | 自动运行 |
| lint-staged | 暂存文件检查 | 自动运行 |

### 11.2 快速命令

```bash
# 安装依赖
npm install

# 运行所有检查
npm run check

# 自动修复
npm run fix

# 运行测试
npm test

# 运行测试 (带覆盖率)
npm run test:coverage
```

### 11.3 ESLint 配置要点

```javascript
// eslint.config.js 主要规则
{
  '@typescript-eslint/no-explicit-any': 'error',     // 禁止 any
  '@typescript-eslint/consistent-type-imports': 'error',  // 类型导入
  'import/order': 'error',                           // 导入排序
  'react-hooks/rules-of-hooks': 'error',             // Hooks 规则
  'react-hooks/exhaustive-deps': 'warn',             // 依赖数组
}
```

### 11.4 Pre-commit 检查

提交代码时自动运行:
1. ESLint 检查并修复
2. Prettier 格式化
3. TypeScript 类型检查

---

## Git 工作流

### 12.1 提交信息规范

```
<type>(<scope>): <subject>

# 示例
feat(chat): 添加消息流式输出功能
fix(ui): 修复按钮在暗色模式下的颜色问题
style(components): 统一组件间距
refactor(stores): 重构 chat store 结构
```

### 12.2 分支命名

```
main                    # 主分支
develop                 # 开发分支
feature/chat-streaming  # 功能分支
fix/button-color        # 修复分支
refactor/store-v2       # 重构分支
```

### 12.3 代码审查清单

- [ ] TypeScript 类型完整，无 any
- [ ] 通过所有 ESLint 检查
- [ ] 代码格式化正确
- [ ] 组件有必要的 Props 类型
- [ ] 有对应的单元测试
- [ ] 遵循项目目录结构
- [ ] 复用现有组件和工具

---

## 附录

### A. 常用类型速查

```typescript
// React 类型
import type { FC, ReactNode, ComponentProps } from 'react'

// 组件 Props
type ButtonProps = ComponentProps<'button'>
type InputProps = ComponentProps<'input'>

// 事件类型
type ClickHandler = (e: React.MouseEvent<HTMLButtonElement>) => void
type ChangeHandler = (e: React.ChangeEvent<HTMLInputElement>) => void
type SubmitHandler = (e: React.FormEvent<HTMLFormElement>) => void

// 子元素
type ChildrenProps = { children: ReactNode }

// 样式
type ClassNameProps = { className?: string }
```

### B. 项目核心类型

```typescript
import type {
  // 基础类型
  User,
  Agent,
  Session,
  Message,

  // 联合类型
  MessageRole,      // 'user' | 'assistant' | 'system' | 'tool'
  ChatEventType,    // 'thinking' | 'text' | 'tool_call' | ...

  // 事件数据
  ChatEvent,
  ToolCall,
  ToolResult,

  // API 类型
  ApiResponse,
  PaginatedResponse,
} from '@/types'
```

### C. 常用工具函数

```typescript
import {
  cn,                  // 合并 className
  formatDate,          // 格式化日期
  formatRelativeTime,  // 相对时间
  truncate,            // 截断字符串
  generateId,          // 生成 ID
} from '@/lib/utils'
```

### D. 相关文档

- [TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/)
- [React TypeScript Cheatsheet](https://react-typescript-cheatsheet.netlify.app/)
- [Tailwind CSS](https://tailwindcss.com/docs)
- [Radix UI](https://www.radix-ui.com/docs)
- [Zustand](https://docs.pmnd.rs/zustand/)
- [React Query](https://tanstack.com/query/latest)

---

<div align="center">

**类型安全 · 组件复用 · 用户体验**

*文档版本: v1.0.0 | 最后更新: 2026-01-12*

</div>
