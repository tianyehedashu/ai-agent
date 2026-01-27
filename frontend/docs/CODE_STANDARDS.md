# Frontend 代码规范

## 核心原则

| 原则             | 说明                                           |
| ---------------- | ---------------------------------------------- |
| **类型安全**     | 禁止 `any`，所有代码必须有完整 TypeScript 类型 |
| **DRY**          | 复用 `@/types`、`@/lib/utils`、shadcn/ui 组件  |
| **单一职责**     | 组件只做一件事，业务逻辑抽离到 hooks           |
| **组合优于继承** | 使用组件组合，避免深层继承                     |

## 项目结构

```
src/
├── api/           # API 调用层
├── components/    # 组件 (ui/ layout/ shared/)
├── hooks/         # 自定义 Hooks
├── lib/           # 工具函数 (utils.ts)
├── pages/         # 页面组件
├── stores/        # Zustand 状态
└── types/         # TypeScript 类型
```

| 目录             | 职责                   |
| ---------------- | ---------------------- |
| `api/`           | HTTP 请求封装          |
| `components/ui/` | 基础 UI (Button, Card) |
| `hooks/`         | 可复用逻辑             |
| `stores/`        | 全局状态               |
| `types/`         | 类型定义               |

## TypeScript 规范

```typescript
// ✅ interface 定义对象，type 定义联合/交叉
interface User {
  id: string
  name: string
}
type MessageRole = 'user' | 'assistant' | 'system'

// ✅ type-only imports
import type { User, Agent } from '@/types'

// ✅ 使用 unknown + 类型守卫替代 any
function process(data: unknown): User {
  if (!isUser(data)) throw new Error('Invalid')
  return data
}
```

## React 组件

```tsx
// 导入顺序: React → 第三方 → 内部组件 → 工具 → 类型
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { User } from '@/types'

// 组件定义
interface UserCardProps {
  user: User
  onSelect?: (user: User) => void
}

export const UserCard = ({ user, onSelect }: UserCardProps) => {
  const [isHovered, setIsHovered] = useState(false)
  return (
    <div className={cn('p-4', isHovered && 'bg-accent')} onClick={() => onSelect?.(user)}>
      {user.name}
    </div>
  )
}
```

## 状态管理

| 场景         | 方案                          |
| ------------ | ----------------------------- |
| 服务端数据   | React Query                   |
| 全局 UI 状态 | Zustand                       |
| 组件局部状态 | useState                      |
| 流式数据     | useRef + useState             |
| 认证状态     | authStore (Zustand + persist) |

### Store 职责分离

```
stores/
├── auth.ts      # 认证状态（token、anonymousUserId）- 持久化到 localStorage
├── user.ts      # 用户信息（currentUser、登录/注册/登出操作）
├── chat.ts      # 聊天状态（messages、session、streaming）
└── sidebar.ts   # 侧边栏 UI 状态
```

| Store       | 职责               | 持久化          |
| ----------- | ------------------ | --------------- |
| `authStore` | Token、匿名用户 ID | ✅ localStorage |
| `userStore` | 用户信息、认证操作 | ❌              |
| `chatStore` | 会话消息、流式内容 | ❌              |

### 认证状态管理

**原则：Token 由 authStore 统一管理，apiClient 从 authStore 获取**

```typescript
// ✅ authStore 管理 token（持久化到 localStorage）
import { useAuthStore, getAuthToken, setAuthToken } from '@/stores/auth'

// 组件中使用（响应式）
const token = useAuthStore((s) => s.token)

// 非 React 环境使用（如 apiClient）
const token = getAuthToken()

// ❌ 直接操作 localStorage
localStorage.getItem('auth_token') // 禁止
```

### Zustand 最佳实践

```typescript
// ✅ 选择性订阅，避免不必要的重渲染
const messages = useChatStore((s) => s.messages)
const token = useAuthStore((s) => s.token)

// ❌ 订阅整个 store（任何状态变化都会触发重渲染）
const store = useChatStore()

// ✅ 使用 persist 中间件持久化关键状态
import { persist, createJSONStorage } from 'zustand/middleware'

const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      /* ... */
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ token: state.token }),
    }
  )
)
```

### React Query

```typescript
// React Query
const { data, isLoading } = useQuery({
  queryKey: ['agents'],
  queryFn: () => agentApi.list(),
})
```

## 样式规范

```tsx
// ✅ 使用 cn() 合并类名
<div className={cn('p-4 rounded-lg', isActive && 'border-primary', className)} />

// ✅ 使用语义化主题变量
'bg-background'  // 不是 'bg-white'
'text-foreground'  // 不是 'text-black'

// ✅ 响应式 (移动优先)
<div className="flex flex-col md:flex-row lg:gap-8">
```

## 性能优化

```tsx
// memo 复杂组件
const MessageItem = memo(({ message }: Props) => <div>{message.content}</div>)

// useMemo 缓存计算
const filtered = useMemo(() => items.filter((x) => x.active), [items])

// 懒加载页面
const ChatPage = lazy(() => import('@/pages/chat'))
```

## 测试规范

```tsx
// 组件测试
describe('Button', () => {
  it('renders children', () => {
    render(<Button>Click</Button>)
    expect(screen.getByText('Click')).toBeInTheDocument()
  })
})

// 运行测试
npm test           # 运行测试
npm run test:cov   # 带覆盖率
```
