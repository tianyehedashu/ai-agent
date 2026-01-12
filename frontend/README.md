# AI Agent Frontend

AI Agent 系统前端应用，基于 React + TypeScript 构建。

## 技术栈

- **框架**: React 18
- **构建工具**: Vite
- **语言**: TypeScript
- **样式**: Tailwind CSS
- **UI 组件**: shadcn/ui + Radix UI
- **状态管理**: Zustand
- **数据请求**: TanStack Query
- **流程可视化**: React Flow
- **代码编辑器**: Monaco Editor

## 项目结构

```
frontend/
├── public/               # 静态资源
├── src/
│   ├── api/             # API 客户端
│   ├── components/      # 组件
│   │   ├── layout/      # 布局组件
│   │   └── ui/          # UI 基础组件
│   ├── hooks/           # 自定义 Hooks
│   ├── lib/             # 工具库
│   ├── pages/           # 页面组件
│   ├── stores/          # Zustand 状态
│   ├── types/           # TypeScript 类型
│   ├── App.tsx          # 应用根组件
│   ├── main.tsx         # 入口文件
│   └── index.css        # 全局样式
├── index.html           # HTML 模板
├── package.json         # 依赖配置
├── tailwind.config.js   # Tailwind 配置
├── tsconfig.json        # TypeScript 配置
└── vite.config.ts       # Vite 配置
```

## 快速开始

### 环境要求

- Node.js 18+
- npm 或 pnpm

### 安装依赖

```bash
npm install
```

### 开发服务器

```bash
npm run dev
```

访问 http://localhost:3000

### 构建生产版本

```bash
npm run build
```

### 预览生产版本

```bash
npm run preview
```

### 运行测试

```bash
npm run test
npm run test:ui  # 带 UI 的测试
npm run test:coverage  # 测试覆盖率
```

## 主要功能

### 对话界面

- 实时流式响应
- Markdown 渲染
- 代码高亮
- 工具调用展示

### Agent 管理

- 创建/编辑/删除 Agent
- 配置模型参数
- 工具选择

### 工作台 (Studio)

- 可视化流程编排
- Code-First 双向同步
- 实时预览

### 设置

- 主题切换
- API 密钥管理
- 账户设置

## 开发规范

### 代码风格

使用 ESLint + Prettier:

```bash
npm run lint
```

### 组件开发

- 使用函数组件 + Hooks
- Props 类型使用 interface 定义
- 复杂状态使用 Zustand

### 文件命名

- 组件: `PascalCase.tsx`
- 工具/钩子: `camelCase.ts`
- 样式: 使用 Tailwind 类名

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `VITE_API_URL` | API 服务地址 | 空 (使用相对路径) |
