# AI Agent 前端设计系统

> 本文档定义了项目的设计语言、视觉规范和组件使用指南，确保 UI 的一致性和可维护性。

## 目录

- [设计原则](#设计原则)
- [色彩系统](#色彩系统)
- [排版系统](#排版系统)
- [间距系统](#间距系统)
- [圆角系统](#圆角系统)
- [阴影系统](#阴影系统)
- [动画系统](#动画系统)
- [图标系统](#图标系统)
- [组件规范](#组件规范)
- [布局规范](#布局规范)
- [响应式设计](#响应式设计)
- [无障碍设计](#无障碍设计)
- [深色模式](#深色模式)

---

## 设计原则

### 核心理念

| 原则 | 说明 |
|------|------|
| **简洁清晰** | 界面简洁，信息层次分明，减少视觉噪音 |
| **一致性** | 统一的视觉语言和交互模式 |
| **响应式** | 移动优先，适配各种屏幕尺寸 |
| **无障碍** | 遵循 WCAG 标准，确保可访问性 |
| **性能优先** | 轻量动画，避免不必要的渲染 |

### 视觉风格

- **现代极简**：清爽的视觉层次，避免过度装饰
- **柔和圆润**：使用圆角和柔和过渡
- **深色优先**：优先考虑深色模式的视觉体验
- **信息密度**：AI Agent 场景需要展示大量信息，保持适度的信息密度

---

## 色彩系统

### 语义化色彩

使用 CSS 变量定义语义化颜色，支持深色/浅色主题切换：

```css
/* 主要颜色变量 */
--background        /* 页面背景 */
--foreground        /* 主要文本 */
--card              /* 卡片背景 */
--card-foreground   /* 卡片文本 */
--primary           /* 主要操作 */
--primary-foreground
--secondary         /* 次要操作 */
--secondary-foreground
--muted             /* 弱化元素 */
--muted-foreground
--accent            /* 强调 */
--accent-foreground
--destructive       /* 危险操作 */
--destructive-foreground
--border            /* 边框 */
--input             /* 输入框边框 */
--ring              /* 聚焦环 */
```

### 浅色主题

| 变量 | HSL 值 | 用途 |
|------|--------|------|
| `--background` | `0 0% 100%` | 纯白背景 |
| `--foreground` | `240 10% 3.9%` | 深灰文本 |
| `--primary` | `240 5.9% 10%` | 深色主色 |
| `--secondary` | `240 4.8% 96%` | 浅灰次要 |
| `--muted` | `240 4.8% 96%` | 弱化背景 |
| `--destructive` | `0 84.2% 60.2%` | 红色警告 |
| `--border` | `240 5.9% 92%` | 浅灰边框 |

### 深色主题

| 变量 | HSL 值 | 用途 |
|------|--------|------|
| `--background` | `240 10% 3.9%` | Zinc 950 深黑 |
| `--foreground` | `0 0% 98%` | 近白文本 |
| `--primary` | `0 0% 98%` | 白色主色 |
| `--secondary` | `240 3.7% 15.9%` | Zinc 800 |
| `--muted` | `240 3.7% 15.9%` | 深灰背景 |
| `--muted-foreground` | `240 5% 64.9%` | Zinc 400 |
| `--border` | `240 3.7% 15.9%` | Zinc 800 边框 |

### 使用规范

```tsx
// ✅ 使用语义化颜色类
<div className="bg-background text-foreground" />
<div className="bg-card border-border" />
<div className="text-muted-foreground" />

// ❌ 禁止硬编码颜色
<div className="bg-white text-black" />
<div className="bg-gray-900" />
<div className="text-gray-500" />
```

### 颜色层次

```
背景层次 (从深到浅/从浅到深)：
┌──────────────────────────────────┐
│  background  - 页面背景          │
│  ┌────────────────────────────┐  │
│  │  card  - 卡片/面板背景     │  │
│  │  ┌──────────────────────┐  │  │
│  │  │  secondary  - 次级区 │  │  │
│  │  └──────────────────────┘  │  │
│  └────────────────────────────┘  │
└──────────────────────────────────┘
```

---

## 排版系统

### 字体家族

```css
--font-sans: "Inter", system-ui, sans-serif;  /* UI 文本 */
--font-mono: "JetBrains Mono", monospace;     /* 代码 */
```

### 字体大小

| 类名 | 大小 | 行高 | 用途 |
|------|------|------|------|
| `text-xs` | 12px | 16px | 辅助信息、标签 |
| `text-sm` | 14px | 20px | 次要文本、描述 |
| `text-base` | 16px | 24px | 正文 |
| `text-lg` | 18px | 28px | 小标题 |
| `text-xl` | 20px | 28px | 二级标题 |
| `text-2xl` | 24px | 32px | 一级标题 |

### 字重

| 类名 | 权重 | 用途 |
|------|------|------|
| `font-normal` | 400 | 正文 |
| `font-medium` | 500 | 按钮、标签 |
| `font-semibold` | 600 | 标题 |
| `font-bold` | 700 | 强调 |

### 使用示例

```tsx
// 页面标题
<h1 className="text-2xl font-semibold leading-none tracking-tight">
  标题
</h1>

// 卡片标题
<h3 className="text-lg font-semibold">卡片标题</h3>

// 描述文本
<p className="text-sm text-muted-foreground">描述内容</p>

// 代码文本
<code className="font-mono text-sm">code snippet</code>
```

---

## 间距系统

### Tailwind 间距值

| 值 | 像素 | 用途 |
|----|------|------|
| `0.5` | 2px | 微小间距 |
| `1` | 4px | 紧凑元素间距 |
| `1.5` | 6px | 小间距 |
| `2` | 8px | 元素内部间距 |
| `3` | 12px | 相关元素组间距 |
| `4` | 16px | 标准间距 |
| `6` | 24px | 区块间距 |
| `8` | 32px | 大区块间距 |

### 组件内部间距

```tsx
// 卡片内部
<Card>
  <CardHeader className="p-6">      {/* 24px 内边距 */}
    <CardTitle className="space-y-1.5">  {/* 6px 垂直间距 */}
  </CardHeader>
  <CardContent className="p-6 pt-0"> {/* 24px 水平, 0 顶部 */}
  </CardContent>
</Card>

// 按钮组
<div className="flex gap-2">  {/* 8px 间距 */}
  <Button />
  <Button />
</div>

// 表单项
<div className="space-y-4">  {/* 16px 垂直间距 */}
  <FormField />
  <FormField />
</div>
```

---

## 圆角系统

### 圆角变量

```css
--radius: 0.75rem;  /* 12px 基准 */

/* 派生值 */
border-radius-lg: var(--radius);           /* 12px */
border-radius-md: calc(var(--radius) - 2px);  /* 10px */
border-radius-sm: calc(var(--radius) - 4px);  /* 8px */
```

### 使用场景

| 类名 | 大小 | 用途 |
|------|------|------|
| `rounded-sm` | 8px | 小按钮、标签 |
| `rounded-md` | 10px | 输入框、按钮 |
| `rounded-lg` | 12px | 卡片、对话框 |
| `rounded-full` | 9999px | 头像、圆形按钮 |

```tsx
// 卡片
<Card className="rounded-lg" />

// 按钮
<Button className="rounded-md" />

// 头像
<Avatar className="rounded-full" />

// 输入框
<Input className="rounded-md" />
```

---

## 阴影系统

### 阴影等级

| 类名 | 用途 |
|------|------|
| `shadow-sm` | 轻微浮起 |
| `shadow` | 卡片默认 |
| `shadow-md` | 下拉菜单 |
| `shadow-lg` | 模态框、悬浮卡 |

### 使用规范

```tsx
// 卡片默认
<Card className="shadow-sm" />

// 下拉菜单
<DropdownMenuContent className="shadow-md" />

// 对话框
<DialogContent className="shadow-lg" />
```

---

## 动画系统

### 预定义动画

```css
/* 手风琴展开/收起 */
animate-accordion-down: 0.2s ease-out
animate-accordion-up: 0.2s ease-out

/* 淡入淡出 */
animate-fade-in: 0.2s ease-out
animate-fade-out: 0.2s ease-out

/* 滑入 */
animate-slide-in-from-top: 0.3s ease-out
animate-slide-in-from-bottom: 0.3s ease-out

/* 脉冲发光 */
animate-pulse-glow: 2s ease-in-out infinite
```

### 过渡时间

| 场景 | 时长 | 曲线 |
|------|------|------|
| 悬停效果 | 150ms | ease-in-out |
| 颜色变化 | 150ms | ease |
| 展开/收起 | 200ms | ease-out |
| 页面过渡 | 300ms | ease-out |
| 复杂动画 | 300-500ms | cubic-bezier |

### 使用示例

```tsx
// 基础过渡
<Button className="transition-colors" />

// 组合过渡
<div className="transition-all duration-200 ease-out" />

// 进入动画
<div className="animate-in animate-fade-in" />

// 打字指示器
<div className="typing-indicator">
  <span /><span /><span />
</div>
```

### Framer Motion

```tsx
import { motion } from 'framer-motion'

// 淡入动画
<motion.div
  initial={{ opacity: 0, y: 8 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.3, ease: [0.2, 0.8, 0.2, 1] }}
/>

// 列表项动画
<motion.div
  variants={{
    hidden: { opacity: 0 },
    show: { opacity: 1 }
  }}
  initial="hidden"
  animate="show"
/>
```

---

## 图标系统

### 图标库

使用 **Lucide React** 作为主要图标库。

```tsx
import { 
  User, Settings, Moon, Sun, Send, 
  ChevronRight, X, Check, AlertCircle 
} from 'lucide-react'
```

### 图标尺寸

| 场景 | 类名 | 尺寸 |
|------|------|------|
| 小型 | `h-4 w-4` | 16px |
| 默认 | `h-5 w-5` | 20px |
| 大型 | `h-6 w-6` | 24px |
| 特大 | `h-8 w-8` | 32px |

### 使用规范

```tsx
// 按钮内图标
<Button>
  <Send className="mr-2 h-4 w-4" />
  发送
</Button>

// 图标按钮
<Button variant="ghost" size="icon">
  <Moon className="h-5 w-5" />
</Button>

// 状态图标
<AlertCircle className="h-4 w-4 text-destructive" />
<Check className="h-4 w-4 text-green-500" />
```

---

## 组件规范

### 按钮 (Button)

#### 变体

| 变体 | 用途 | 视觉 |
|------|------|------|
| `default` | 主要操作 | 实心背景 |
| `secondary` | 次要操作 | 灰色背景 |
| `outline` | 边框样式 | 透明背景+边框 |
| `ghost` | 工具栏按钮 | 透明背景 |
| `destructive` | 危险操作 | 红色背景 |
| `link` | 链接样式 | 下划线 |

#### 尺寸

| 尺寸 | 高度 | 用途 |
|------|------|------|
| `sm` | 36px | 紧凑场景 |
| `default` | 40px | 默认 |
| `lg` | 44px | 强调 |
| `icon` | 40x40px | 图标按钮 |

```tsx
// 主要操作
<Button>提交</Button>

// 次要操作
<Button variant="secondary">取消</Button>

// 危险操作
<Button variant="destructive">删除</Button>

// 图标按钮
<Button variant="ghost" size="icon">
  <Settings className="h-5 w-5" />
</Button>
```

### 卡片 (Card)

```tsx
<Card>
  <CardHeader>
    <CardTitle>标题</CardTitle>
    <CardDescription>描述文本</CardDescription>
  </CardHeader>
  <CardContent>
    {/* 内容 */}
  </CardContent>
  <CardFooter>
    {/* 操作按钮 */}
  </CardFooter>
</Card>
```

### 输入框 (Input)

```tsx
// 基础输入
<Input placeholder="请输入..." />

// 带标签
<div className="space-y-2">
  <Label htmlFor="email">邮箱</Label>
  <Input id="email" type="email" />
</div>

// 禁用状态
<Input disabled placeholder="不可编辑" />
```

### 对话框 (Dialog)

```tsx
<Dialog>
  <DialogTrigger asChild>
    <Button>打开</Button>
  </DialogTrigger>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>标题</DialogTitle>
      <DialogDescription>描述</DialogDescription>
    </DialogHeader>
    {/* 内容 */}
    <DialogFooter>
      <Button variant="outline">取消</Button>
      <Button>确认</Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

---

## 布局规范

### 页面布局

```
┌─────────────────────────────────────────────────┐
│  Header (h-14, sticky top-0)                    │
├───────────┬─────────────────────────────────────┤
│           │                                     │
│  Sidebar  │        Main Content                 │
│  (w-64)   │                                     │
│           │                                     │
│           │                                     │
│           │                                     │
└───────────┴─────────────────────────────────────┘
```

### Header 规范

- 高度: `h-14` (56px)
- 固定定位: `sticky top-0 z-50`
- 背景: `bg-background/95 backdrop-blur`
- 边框: `border-b border-border/40`
- 水平内边距: `px-6`

### Sidebar 规范

- 宽度: `w-64` (256px)
- 可收起
- 边框: `border-r border-border/40`

### 容器

```tsx
// 居中容器 (最大 1400px)
<div className="container">
  {/* 内容 */}
</div>

// 全宽容器
<div className="w-full px-6">
  {/* 内容 */}
</div>
```

---

## 响应式设计

### 断点

| 前缀 | 最小宽度 | 目标设备 |
|------|----------|----------|
| (默认) | 0px | 移动端 |
| `sm` | 640px | 小平板 |
| `md` | 768px | 平板 |
| `lg` | 1024px | 笔记本 |
| `xl` | 1280px | 桌面 |
| `2xl` | 1400px | 大屏 |

### 移动优先

```tsx
// 移动: 垂直排列，桌面: 水平排列
<div className="flex flex-col md:flex-row">
  {/* 内容 */}
</div>

// 移动: 单列，桌面: 三列
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  {/* 内容 */}
</div>

// 移动: 隐藏侧边栏
<aside className="hidden md:block w-64">
  {/* 侧边栏 */}
</aside>
```

---

## 无障碍设计

### 基本原则

1. **键盘可访问**: 所有交互元素可通过键盘操作
2. **焦点可见**: 明确的焦点状态
3. **语义化标签**: 使用正确的 HTML 标签
4. **对比度**: 文本与背景有足够的对比度

### 焦点样式

```tsx
// 所有可交互元素应有焦点环
className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
```

### ARIA 属性

```tsx
// 对话框
<Dialog>
  <DialogContent aria-describedby="dialog-description">
    <DialogTitle>标题</DialogTitle>
    <DialogDescription id="dialog-description">
      描述
    </DialogDescription>
  </DialogContent>
</Dialog>

// 加载状态
<Button disabled aria-busy="true">
  <Loader className="animate-spin" aria-hidden="true" />
  加载中...
</Button>
```

---

## 深色模式

### 实现方式

使用 `class` 策略，在 `<html>` 标签添加 `dark` 类：

```tsx
// ThemeProvider 管理主题
const { theme, setTheme } = useTheme()

// 切换主题
<Button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
  {theme === 'dark' ? <Sun /> : <Moon />}
</Button>
```

### 深色模式设计原则

1. **降低亮度对比**: 不使用纯白 (#fff)，使用 `--foreground` (近白)
2. **适当降低饱和度**: 深色模式下颜色稍微降低饱和度
3. **阴影调整**: 深色模式下阴影效果减弱
4. **边框可见性**: 确保边框在深色背景下可见

### 条件样式

```tsx
// 深色模式特定样式
<div className="bg-white dark:bg-card" />
<div className="text-gray-900 dark:text-gray-100" />

// 一般情况使用语义化颜色变量，自动适配
<div className="bg-background text-foreground" />
```

---

## 工具函数

### cn() 类名合并

```tsx
import { cn } from '@/lib/utils'

// 合并类名，处理冲突
<div className={cn(
  'p-4 rounded-lg',         // 基础样式
  isActive && 'bg-accent',  // 条件样式
  className                  // 外部传入
)} />
```

### CVA 变体系统

```tsx
import { cva, type VariantProps } from 'class-variance-authority'

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-md',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground',
        secondary: 'bg-secondary text-secondary-foreground',
      },
      size: {
        default: 'h-10 px-4',
        sm: 'h-9 px-3',
        lg: 'h-11 px-8',
      }
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    }
  }
)

// 使用
<button className={cn(buttonVariants({ variant, size }), className)} />
```

---

## 检查清单

### 组件开发检查

- [ ] 使用语义化颜色变量
- [ ] 支持深色模式
- [ ] 添加适当的过渡动画
- [ ] 焦点状态可见
- [ ] 响应式适配
- [ ] TypeScript 类型完整
- [ ] 使用 cn() 合并类名

### 页面开发检查

- [ ] 页面标题正确设置
- [ ] 加载状态处理
- [ ] 错误状态处理
- [ ] 空状态处理
- [ ] 移动端适配
- [ ] 键盘导航支持

---

## 更新日志

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| 1.0.0 | 2026-01-29 | 初始版本 |
