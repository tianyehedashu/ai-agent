---
name: frontend-code-check
model: inherit
description: 识别并修复前端 ESLint/TypeScript 错误
---

修复 ESLint 和 TypeScript 检查报告的问题，确保代码质量符合项目规范和软件工程最佳实践。

## 核心原则

1. **简单问题直接修复** — 明确的代码风格、命名、格式问题快速处理
2. **复杂问题深度分析** — 难修复的问题需识别是否是架构设计不合理导致
3. **修复质量保证** — 不破坏功能、不简单注释、不防御编程、找到根本原因

## 软件工程原则

| 原则 | 说明 | 实践 |
|------|------|------|
| **DRY** | Don't Repeat Yourself - 避免重复代码 | 复用 `@/types`、`@/lib/utils`、shadcn/ui 组件、自定义 Hooks |
| **单一职责** | Single Responsibility - 每个模块只做一件事 | 组件只负责 UI，业务逻辑抽离到 Hooks，状态管理分离 |
| **组合优于继承** | Composition over Inheritance | 使用组件组合、Hooks 组合，避免深层继承 |
| **类型安全** | Type Safety - 完整的类型系统 | 禁止 `any`，使用 `unknown` + 类型守卫，明确的函数返回类型 |
| **关注点分离** | Separation of Concerns | API 层、组件层、状态层、工具层职责清晰 |

### DRY 实践示例

```typescript
// ❌ 错误：重复的类型定义
interface UserCardProps { user: { id: string; name: string } }
interface UserListProps { users: { id: string; name: string }[] }

// ✅ 正确：复用类型定义
import type { User } from '@/types'
interface UserCardProps { user: User }
interface UserListProps { users: User[] }

// ❌ 错误：重复的工具函数
function formatDate1(date: Date) { return date.toISOString() }
function formatDate2(date: Date) { return date.toISOString() }

// ✅ 正确：提取到 utils
import { formatDate } from '@/lib/utils'
```

### 单一职责实践示例

```typescript
// ❌ 错误：组件承担过多职责
function UserCard({ user }: Props) {
  const [data, setData] = useState(null)
  useEffect(() => { fetchData(user.id).then(setData) }, [user.id])
  const handleClick = () => { /* 复杂业务逻辑 */ }
  return <div onClick={handleClick}>...</div>
}

// ✅ 正确：职责分离
function UserCard({ user }: Props) {
  const { data, handleClick } = useUserCard(user.id)
  return <div onClick={handleClick}>...</div>
}

function useUserCard(userId: string) {
  const [data, setData] = useState(null)
  useEffect(() => { fetchData(userId).then(setData) }, [userId])
  const handleClick = useCallback(() => { /* 业务逻辑 */ }, [])
  return { data, handleClick }
}
```

## 技术栈

| 类别 | 技术 |
|------|------|
| 框架 | React 18 + TypeScript |
| 构建工具 | Vite |
| 状态管理 | Zustand（全局状态）+ React Query（服务端数据） |
| UI 组件 | Radix UI + shadcn/ui + Tailwind CSS |
| 路由 | React Router v6 |
| 代码检查 | ESLint + TypeScript + Prettier |
| 测试 | Vitest + Testing Library |

## 执行流程

### 1. 运行代码检查

```bash
cd frontend

# 完整检查（类型 + ESLint + 格式化）
npm run check

# 自动修复
npm run fix          # ESLint 修复 + Prettier 格式化
npm run lint:fix     # 仅 ESLint 修复
```

### 2. 问题分类与修复

#### 简单问题（直接修复）

| 问题类型 | ESLint 规则 | 修复方式 |
|---------|------------|---------|
| 使用 `any` | `@typescript-eslint/no-explicit-any` | 使用具体类型或 `unknown` + 类型守卫 |
| 未使用变量 | `@typescript-eslint/no-unused-vars` | 删除或使用 `_` 前缀 |
| 导入顺序 | `import/order` | React → 第三方 → 内部 → 工具 → 类型 |
| 缺少类型导入 | `@typescript-eslint/consistent-type-imports` | 使用 `import type` |
| 使用 `==` | `eqeqeq` | 改为 `===` |
| 缺少可选链 | `@typescript-eslint/prefer-optional-chain` | 使用 `?.` 和 `??` |

#### 中等问题（需分析）

| 问题类型 | 分析要点 |
|---------|---------|
| 缺少返回类型 | 为函数添加明确的返回类型注解 |
| 未处理的 Promise | 使用 `await`、`.catch()` 或 `void` 明确处理 |
| React Hooks 依赖缺失 | 添加依赖项或使用 `useCallback`/`useMemo` |

#### 架构问题（需深度分析）

| 问题类型 | 可能的根本原因 |
|---------|---------------|
| 循环依赖 | 模块职责不清、分层不合理 |
| 组件职责过多 | 需要拆分为更小的组件或提取 hooks |
| 状态管理不当 | 状态应该放在合适的层级（组件/Store/URL） |

## 状态管理规范

### 状态选择原则

| 场景 | 方案 | 示例 |
|------|------|------|
| 服务端数据 | React Query | `useQuery(['agents'], agentApi.list)` |
| 全局 UI 状态 | Zustand | `useAuthStore((s) => s.token)` |
| 组件局部状态 | `useState` | `const [isOpen, setIsOpen] = useState(false)` |
| 流式数据 | `useRef` + `useState` | SSE/WebSocket 流式响应 |

### Zustand 使用规范

```typescript
// ✅ 选择性订阅，避免不必要的重渲染
const token = useAuthStore((s) => s.token)
const messages = useChatStore((s) => s.messages)

// ❌ 订阅整个 store
const store = useChatStore()  // 任何状态变化都会触发重渲染

// ✅ 非 React 环境使用 getState
const token = useAuthStore.getState().token  // 如 apiClient
```

### Store 职责分离

| Store | 职责 | 持久化 |
|-------|------|--------|
| `authStore` | Token、匿名用户 ID | ✅ localStorage |
| `userStore` | 用户信息、认证操作 | ❌ |
| `chatStore` | 会话消息、流式内容 | ❌ |
| `sidebarStore` | 侧边栏 UI 状态 | ❌ |

**禁止直接操作 localStorage**：
```typescript
// ❌ 错误
localStorage.getItem('auth_token')

// ✅ 正确
import { getAuthToken } from '@/stores/auth'
const token = getAuthToken()
```

### React Query 使用规范

```typescript
// ✅ 服务端数据查询
const { data, isLoading, error } = useQuery({
  queryKey: ['agents', agentId],
  queryFn: () => agentApi.get(agentId),
  enabled: !!agentId,  // 条件查询
})

// ✅ 数据变更
const mutation = useMutation({
  mutationFn: agentApi.create,
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['agents'] })
  },
})
```

## Hooks 使用规范

### 自定义 Hooks 原则

1. **单一职责** — 一个 Hook 只做一件事
2. **命名规范** — 以 `use` 开头，如 `useChat`、`useToast`
3. **类型安全** — 明确的输入输出类型
4. **依赖管理** — 正确使用 `useCallback`、`useMemo`、依赖数组

### Hook 定义模板

```typescript
interface UseChatOptions {
  sessionId?: string
  onError?: (error: Error) => void
}

interface UseChatReturn {
  messages: Message[]
  isLoading: boolean
  sendMessage: (content: string) => Promise<void>
  clearMessages: () => void
}

export function useChat(options: UseChatOptions = {}): UseChatReturn {
  const { sessionId, onError } = options
  
  // 状态
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  
  // 方法使用 useCallback 优化
  const sendMessage = useCallback(async (content: string) => {
    // ...
  }, [sessionId])
  
  const clearMessages = useCallback(() => {
    setMessages([])
  }, [])
  
  return { messages, isLoading, sendMessage, clearMessages }
}
```

### React Hooks 规则

```typescript
// ✅ 正确：在顶层调用，条件在内部
function Component() {
  const [count, setCount] = useState(0)
  const data = useQuery(...)
  
  if (count > 0) {
    // 条件逻辑在内部
  }
}

// ❌ 错误：条件调用 Hook
if (condition) {
  const data = useQuery(...)  // 违反 Rules of Hooks
}

// ✅ 正确：依赖数组完整
useEffect(() => {
  fetchData(id)
}, [id])  // 包含所有依赖

// ✅ 正确：使用 useCallback 避免依赖问题
const handleClick = useCallback(() => {
  doSomething(id)
}, [id])
```

## Tailwind CSS 使用规范

### 类名合并

```typescript
// ✅ 使用 cn() 工具函数合并类名
import { cn } from '@/lib/utils'

<div className={cn('p-4 rounded-lg', isActive && 'border-primary', className)} />

// ❌ 错误：直接拼接字符串
<div className={'p-4 ' + (isActive ? 'border-primary' : '')} />
```

### 语义化主题变量

```typescript
// ✅ 使用语义化变量（支持暗色模式）
'bg-background'      // 不是 'bg-white' 或 'bg-gray-50'
'text-foreground'    // 不是 'text-black' 或 'text-gray-900'
'border-border'      // 不是 'border-gray-200'
'text-primary'       // 主题主色

// ❌ 错误：硬编码颜色值
'bg-white dark:bg-gray-900'  // 应该使用 'bg-background'
```

### 响应式设计（移动优先）

```typescript
// ✅ 移动优先：基础样式 + 断点样式
<div className="flex flex-col md:flex-row lg:gap-8">
  <div className="w-full md:w-1/2 lg:w-1/3" />
</div>

// ✅ 使用容器查询（如需要）
<div className="@container">
  <div className="@md:flex" />
</div>
```

### 常用模式

```typescript
// ✅ 条件样式
<div className={cn('base-classes', condition && 'conditional-classes')} />

// ✅ 状态样式
<button className={cn(
  'base',
  isActive && 'active',
  isDisabled && 'disabled'
)} />

// ✅ 组合样式
<div className="flex items-center gap-2 p-4 rounded-lg bg-card">
```

## shadcn/ui 使用规范

### 组件导入

```typescript
// ✅ 从 @/components/ui 导入
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogTrigger } from '@/components/ui/dialog'

// ❌ 错误：不要从 node_modules 导入
import { Button } from '@radix-ui/react-button'  // 应该使用 shadcn/ui 封装
```

### 组件变体使用

```typescript
// ✅ 使用组件提供的变体
<Button variant="default" size="lg">提交</Button>
<Button variant="outline" size="sm">取消</Button>
<Button variant="ghost" size="icon">
  <Icon />
</Button>

// ❌ 错误：直接覆盖组件样式（除非必要）
<Button className="bg-red-500">  // 应该使用 variant="destructive"
```

### 组件组合

```typescript
// ✅ 使用 shadcn/ui 组件组合
<Card>
  <CardHeader>
    <CardTitle>标题</CardTitle>
  </CardHeader>
  <CardContent>
    <Button>操作</Button>
  </CardContent>
</Card>

// ✅ 使用 asChild 模式（组合 Radix UI）
<Dialog>
  <DialogTrigger asChild>
    <Button variant="outline">打开</Button>
  </DialogTrigger>
  <DialogContent>
    {/* 内容 */}
  </DialogContent>
</Dialog>
```

### 自定义组件样式

```typescript
// ✅ 通过 className prop 扩展样式
<Button className="w-full md:w-auto">按钮</Button>

// ✅ 使用 cn() 合并组件默认样式
<Button className={cn(buttonVariants(), 'custom-class')} />

// ❌ 错误：直接修改组件源码（应该 fork 或扩展）
```

### 组件扩展原则

1. **优先使用现有变体** — 使用组件提供的 `variant` 和 `size`
2. **通过 className 扩展** — 使用 `className` prop 添加额外样式
3. **必要时 fork 组件** — 如需大幅修改，复制到 `components/` 目录自定义

## 禁止行为 ❌

### 1. 禁止使用 `any` 类型

```typescript
// ❌ 错误
function process(data: any): any {
  return data.value
}

// ✅ 正确：使用 unknown + 类型守卫
function process(data: unknown): string {
  if (isData(data)) {
    return data.value
  }
  throw new Error('Invalid data')
}
```

### 2. 禁止简单注释抑制

```typescript
// ❌ 错误：简单添加 eslint-disable
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function process(data: any) { }

// ✅ 正确：修复类型问题
function process(data: unknown): string { }
```

**例外**：仅当误报或与项目特殊需求冲突时，需在注释中说明原因。

### 3. 禁止直接操作 localStorage

```typescript
// ❌ 错误
localStorage.getItem('auth_token')

// ✅ 正确：通过 authStore 统一管理
import { getAuthToken } from '@/stores/auth'
const token = getAuthToken()
```

## 验证完成标准

修复完成后必须满足：

1. ✅ `npm run check` 通过（类型检查 + ESLint + 格式化）
2. ✅ 相关测试通过（`npm test`）
3. ✅ 代码功能未被破坏
4. ✅ 构建成功（`npm run build`）

## 相关资源

- ESLint 配置：`frontend/eslint.config.js`
- TypeScript 配置：`frontend/tsconfig.json`
- 代码规范：`frontend/docs/CODE_STANDARDS.md`
