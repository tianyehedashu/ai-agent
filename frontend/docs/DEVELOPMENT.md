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

管理端页面位于 `src/pages/gateway/`。团队工作区以 URL `/gateway/teams/:teamId/*` 为 SSOT；无 `:teamId` 的扁平路由（调用指南、侧栏导航链接等）默认使用 **personal team**，不在 UI 提供全局团队切换。浏览器管理 API **不**发送 `X-Team-Id`（团队由路径参数选定）；外部 `/v1/*` 代理的 `sk-*` 才需 `X-Team-Id`。后端领域架构、RBAC 与分区表注意事项见仓库根目录下后端文档：

[`backend/docs/AI_GATEWAY_DOMAIN_ARCHITECTURE.md`](../../backend/docs/AI_GATEWAY_DOMAIN_ARCHITECTURE.md)

### 虚拟 Key（`sk-gw-*`）与平台 API Key（`sk-*`）

产品说明集中在文档，控制台页面仅保留标题、团队徽章与操作，不在 UI 重复展开下列规则。

| 形态             | 前缀      | 创建入口                                                    | 团队上下文                                                                                 | 适用入口                        |
| ---------------- | --------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------ | ------------------------------- |
| **虚拟 Key**     | `sk-gw-*` | AI 网关 → 虚拟 Key                                          | **创建时绑定**当前团队；代理 `/v1/*` **勿传** `X-Team-Id`（传入且与 Key 团队不一致时 400） | OpenAI / Anthropic 兼容 `/v1/*` |
| **平台 API Key** | `sk-*`    | 设置 → API 密钥（需 `gateway:proxy` scope + Gateway grant） | 请求头 `X-Team-Id` 选择 **已授权**团队；缺省优先 personal grant                            | 同上，且可复用其他 API 能力     |

**模型可见性**：客户端请求中的 `model` 须在该 Key 绑定团队的「模型管理」中注册且凭据可用；控制台试调与管理 API 使用 URL 或 personal 工作区团队上下文。

**产品对话（Chat）**：模型下拉与发送均携带 `gateway_team_id`（默认 `useGatewayWorkspaceTeamId()` 解析的 personal 工作区），对应 `GET /api/v1/gateway/models/available?gateway_team_id=…` 与 `POST /api/v1/chat` 请求体中的同名字段；与调用指南 Playground 在未选凭据时的默认团队语义一致。

**控制台 vs 代理**：

- 管理面 `GET/POST … /api/v1/gateway/teams/{team_id}/*`：JWT + 路径 `team_id`，**不**依赖 `X-Team-Id`。
- 对外代理 `/v1/*`：`sk-gw-*` 团队已写入 Key；`sk-*` 须通过 grant + `X-Team-Id` 选定团队。

**进一步阅读**：

- [`backend/docs/AI_GATEWAY_DOMAIN_ARCHITECTURE.md`](../../backend/docs/AI_GATEWAY_DOMAIN_ARCHITECTURE.md) — 鉴权矩阵、grant、日志聚合
- [`backend/docs/项目权限规则.md`](../../backend/docs/项目权限规则.md) — §平台 Key vs 虚拟 Key、虚拟 Key 创建者隔离
- [`backend/docs/gateway/GATEWAY_CURSOR_CLAUDE_CODE.md`](../../backend/docs/gateway/GATEWAY_CURSOR_CLAUDE_CODE.md) — Cursor / Claude Code 集成
- [`backend/docs/gateway/GATEWAY_THIRDPARTY_CLIENT_GUIDE.md`](../../backend/docs/gateway/GATEWAY_THIRDPARTY_CLIENT_GUIDE.md) — 第三方客户端快速上手

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
