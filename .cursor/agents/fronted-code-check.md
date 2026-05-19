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

## 前端目录结构规范

### 标准目录职责

```text
frontend/src/
├── api/           # API 调用层：HTTP 封装、请求/响应类型、后端接口适配
├── components/    # 跨业务通用组件：ui/、layout/、shared/、chat/ 等
├── constants/     # 跨模块常量；仅放稳定、无副作用的配置值
├── features/      # 按业务功能分包：Gateway、模型、凭据、用量等可复用业务块
├── hooks/         # 跨业务可复用 Hooks；单功能私有 Hooks 留在 feature 内
├── lib/           # 通用工具函数；不得承载业务规则
├── pages/         # 路由页面：组合 features、处理页面级布局和路由参数
├── stores/        # Zustand 全局状态；避免组件直接操作 localStorage
├── styles/        # 全局样式或主题入口（如存在）
└── types/         # 全局 TypeScript 类型；局部类型优先就近定义
```

| 目录 | 放置规则 | 禁止事项 |
|------|---------|---------|
| `api/` | 统一封装后端接口、DTO 转换、错误归一化 | 在组件里散落 `fetch`/`axios` 调用或重复定义接口类型 |
| `components/ui/` | shadcn/ui 基础组件与轻量扩展 | 写入业务逻辑、调用 API、读取 store |
| `components/layout/` | 应用壳、导航、侧栏、顶部栏等布局组件 | 混入具体业务表单和请求逻辑 |
| `components/shared/` | 多业务复用的无领域组件 | 放只被单个 feature 使用的组件 |
| `features/<feature>/` | 功能内组件、Hooks、工具、测试、局部类型 | 被 `pages/` 或其他 feature 复制实现同一业务规则 |
| `pages/` | 路由入口和页面编排，优先组合 `features/` | 堆积复杂业务逻辑、长表单状态、API 细节 |
| `stores/` | 认证、偏好、跨页面选择等全局状态 | 存放服务端数据缓存；服务端数据用 React Query |
| `types/` | 多模块共享类型、后端公共响应类型 | 为单个组件的 props 创建全局类型 |

### Feature 分包约定

**默认就近，复用后上提；先 feature 内聚，再抽公共层。**

```text
features/gateway-playground/
├── modes/                     # 子模式组件；仅服务当前 feature
├── playground-card.tsx         # feature 主组件
├── playground-request.ts       # 请求组装/领域逻辑
├── playground-request.test.ts  # 与逻辑文件同目录测试
├── use-playground-call.ts      # feature 私有 Hook
└── types.ts                    # feature 内共享类型
```

1. **业务内聚**：同一功能的 UI、Hook、工具、测试优先放在同一个 `features/<feature>/` 下。
2. **页面只编排**：`pages/gateway/*` 这类路由页面负责权限、URL 参数、布局和 feature 组合；复杂逻辑下沉到 `features/gateway-*`。
3. **测试就近**：新增逻辑文件、Hook 或复杂组件时，测试文件与被测文件同目录，命名为 `*.test.ts` 或 `*.test.tsx`。
4. **类型就近**：只在当前 feature 内复用的类型放 `features/<feature>/types.ts`；跨 feature 复用后再提升到 `types/`。
5. **避免反向依赖**：`features/` 可以引用 `api/`、`components/`、`hooks/`、`lib/`、`stores/`、`types/`；禁止通用层反向引用具体 feature。

### 放置决策

| 需求 | 优先放置位置 |
|------|-------------|
| 新增后端接口调用 | `api/<domain>.ts`，必要时补 `api/<domain>.test.ts` |
| 新增路由页面 | `pages/<domain>/<page>.tsx`，页面组合 feature 组件 |
| 新增业务组件 | `features/<feature>/<component>.tsx` |
| 新增跨业务 UI 组件 | `components/shared/`；基础控件放 `components/ui/` |
| 新增业务 Hook | 单 feature 使用放 `features/<feature>/use-*.ts`；跨业务复用放 `hooks/` |
| 新增状态 | 服务端数据用 React Query；跨页面客户端状态放 `stores/`；局部状态留组件内 |
| 新增工具函数 | 纯通用工具放 `lib/`；业务规则放对应 `features/<feature>/` |

### 命名与导入

```typescript
// ✅ 使用路径别名，避免深层相对路径
import { Button } from '@/components/ui/button'
import { gatewayApi } from '@/api/gateway'
import type { GatewayModel } from '@/types'

// ✅ feature 内部可以相对导入同目录模块
import { buildPlaygroundRequest } from './playground-request'
```

1. 文件名使用 kebab-case：`playground-output-panel.tsx`、`use-playground-call.ts`。
2. React 组件导出使用 PascalCase，Hook 使用 `useXxx`，工具函数使用动词短语。
3. 跨目录导入优先使用 `@/` 别名；同目录或同 feature 的近邻文件可使用相对路径。
4. 禁止从 `pages/` 导入业务逻辑；可复用逻辑必须先下沉到 `features/`、`hooks/`、`lib/` 或 `api/`。
5. 禁止引入新的重复目录或拼写错误目录；例如前端检查 Agent 文件名如需新增，应统一为 `frontend-*`，避免 `fronted-*` 继续扩散。

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
