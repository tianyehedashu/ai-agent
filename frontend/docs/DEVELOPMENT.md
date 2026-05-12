# 🚀 前端开发者快速入门

## 环境要求

- Node.js 18+
- npm 9+ / pnpm 8+

## 快速开始

### 1. 安装依赖

```bash
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:3000

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件
VITE_API_URL=http://localhost:8000
```

## AI Gateway 控制台（可选）

管理端页面位于 `src/pages/gateway/`，团队上下文由 `src/stores/gateway-team.ts` 写入 **`X-Team-Id`**。后端领域架构、RBAC 与分区表注意事项见仓库根目录下后端文档：

[`backend/docs/AI_GATEWAY_DOMAIN_ARCHITECTURE.md`](../../backend/docs/AI_GATEWAY_DOMAIN_ARCHITECTURE.md)

## 常用命令

```bash
# 开发
npm run dev           # 启动开发服务器
npm run build         # 构建生产版本
npm run preview       # 预览生产构建

# 代码质量
npm run check         # 运行所有检查 (类型 + Lint + 格式)
npm run lint          # 运行 ESLint
npm run lint:fix      # 自动修复 ESLint 问题
npm run format        # 格式化代码
npm run typecheck     # TypeScript 类型检查

# 测试
npm test              # 运行测试 (watch 模式)
npm run test:run      # 单次运行测试
npm run test:ui       # 测试 UI 界面
npm run test:coverage # 覆盖率报告
```

## 项目结构

```
src/
├── api/          # API 调用层
├── components/   # 组件
│   ├── ui/       # 基础 UI 组件
│   └── layout/   # 布局组件
├── hooks/        # 自定义 Hooks
├── lib/          # 工具函数
├── pages/        # 页面组件
├── stores/       # Zustand 状态存储
└── types/        # TypeScript 类型
```

## 技术栈

| 技术         | 用途       |
| ------------ | ---------- |
| React 18     | UI 框架    |
| TypeScript   | 类型安全   |
| Vite         | 构建工具   |
| Tailwind CSS | 样式       |
| Radix UI     | 无样式组件 |
| Zustand      | 状态管理   |
| React Query  | 数据获取   |
| React Router | 路由       |
| Zod          | 表单验证   |
| Vitest       | 测试       |

## 添加新组件

### 1. UI 组件 (基础)

```bash
# 放在 src/components/ui/
src/components/ui/new-component.tsx
```

### 2. 业务组件

```bash
# 放在页面目录下
src/pages/chat/components/message-item.tsx
```

### 3. 共享业务组件

```bash
# 放在 src/components/shared/
src/components/shared/user-avatar.tsx
```

## 添加新页面

```tsx
// src/pages/new-page/index.tsx
export default function NewPage() {
  return (
    <div className="p-6">
      <h1>新页面</h1>
    </div>
  )
}

// 在 App.tsx 中添加路由
;<Route path="/new-page" element={<NewPage />} />
```

## 状态管理

### Zustand Store

```tsx
// stores/example.ts
import { create } from 'zustand'

interface ExampleState {
  count: number
  increment: () => void
}

export const useExampleStore = create<ExampleState>((set) => ({
  count: 0,
  increment: () => set((state) => ({ count: state.count + 1 })),
}))

// 使用
const count = useExampleStore((state) => state.count)
const increment = useExampleStore((state) => state.increment)
```

### React Query

```tsx
// hooks/use-example.ts
import { useQuery } from '@tanstack/react-query'

export function useExamples() {
  return useQuery({
    queryKey: ['examples'],
    queryFn: () => api.getExamples(),
  })
}
```

## 相关文档

- [代码规范](./CODE_STANDARDS.md) - 详细的代码规范说明
- [TypeScript 手册](https://www.typescriptlang.org/docs/)
- [Tailwind CSS](https://tailwindcss.com/docs)
- [Radix UI](https://www.radix-ui.com/docs)
