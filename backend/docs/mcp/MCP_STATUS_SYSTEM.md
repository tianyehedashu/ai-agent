# MCP 服务器状态系统 - 前后端统一规范

## 状态定义

MCP 服务器的状态由两个维度决定：

1. **enabled**: 服务器是否启用（用户可控）
2. **connection_status**: 连接状态（系统自动检测）

## 状态组合

| enabled | connection_status | overall_status | status_color | status_text | 说明 |
|---------|------------------|----------------|--------------|-------------|------|
| `false` | any | `disabled` | `gray` | `已禁用` | 服务器已禁用，无法使用 |
| `true` | `connected` | `connected` | `green` | `已连接` | 服务器启用且连接成功 ✅ |
| `true` | `failed` | `failed` | `red` | `连接失败` | 服务器启用但连接失败 ❌ |
| `true` | `unknown` | `unknown` | `yellow` | `未测试` | 服务器启用但未测试过 ⚠️ |
| `true` | `null` | `unknown` | `yellow` | `未测试` | 服务器刚创建，未测试 ⚠️ |

## 颜色规范

### 前端颜色映射（Tailwind CSS）

```typescript
const statusColorMap = {
  gray: 'bg-gray-100 text-gray-600 border-gray-300',
  green: 'bg-green-100 text-green-600 border-green-300',
  red: 'bg-red-100 text-red-600 border-red-300',
  yellow: 'bg-yellow-100 text-yellow-600 border-yellow-300',
};

const statusIconMap = {
  gray: '⚪',
  green: '🟢',
  red: '🔴',
  yellow: '🟡',
};
```

### CSS 变量定义

```css
:root {
  /* MCP 状态颜色 */
  --mcp-status-gray: #9ca3af;    /* 禁用 */
  --mcp-status-green: #22c55e;    /* 已连接 */
  --mcp-status-red: #ef4444;      /* 连接失败 */
  --mcp-status-yellow: #eab308;   /* 未测试 */

  /* MCP 状态背景色 */
  --mcp-bg-gray: #f3f4f6;
  --mcp-bg-green: #dcfce7;
  --mcp-bg-red: #fee2e2;
  --mcp-bg-yellow: #fef9c3;
}
```

## 后端 API

### MCPServerResponse

```typescript
interface MCPServerResponse {
  id: string;
  name: string;
  display_name: string | null;
  url: string;
  scope: 'system' | 'user';
  env_type: string;
  env_config: Record<string, any>;
  enabled: boolean;
  connection_status: 'connected' | 'failed' | 'unknown' | null;
  last_connected_at: string | null;  // ISO 格式
  last_error: string | null;
  available_tools: {
    tools: Array<{name: string; description: string}>;
    count: number;
    updated_at: string;
  };
  created_at: string;
  updated_at: string;
  user_id: string | null;

  // 计算字段（自动生成）
  overall_status: 'disabled' | 'connected' | 'failed' | 'unknown';
  status_color: 'gray' | 'green' | 'red' | 'yellow';
  status_text: '已禁用' | '已连接' | '连接失败' | '未测试';
}
```

### API 响应示例

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "filesystem",
  "display_name": "文件系统",
  "url": "stdio://npx -y @modelcontextprotocol/server-filesystem",
  "scope": "system",
  "env_type": "preinstalled",
  "env_config": {"allowedDirectories": ["."]},
  "enabled": true,
  "connection_status": "connected",
  "last_connected_at": "2026-01-27T16:30:00",
  "last_error": null,
  "available_tools": {
    "tools": [
      {"name": "read_file", "description": "读取文件内容"},
      {"name": "write_file", "description": "写入文件内容"}
    ],
    "count": 2,
    "updated_at": "2026-01-27T16:30:00"
  },
  "created_at": "2026-01-27T15:00:00",
  "updated_at": "2026-01-27T16:30:00",
  "user_id": null,

  // 计算字段
  "overall_status": "connected",
  "status_color": "green",
  "status_text": "已连接"
}
```

## 前端集成

### TypeScript 类型定义

```typescript
// frontend/src/types/mcp.ts
export type MCPStatus = 'disabled' | 'connected' | 'failed' | 'unknown';
export type MCPStatusColor = 'gray' | 'green' | 'red' | 'yellow';

export interface MCPServer {
  id: string;
  name: string;
  display_name: string | null;
  url: string;
  scope: 'system' | 'user';
  env_type: string;
  env_config: Record<string, any>;
  enabled: boolean;
  connection_status: 'connected' | 'failed' | 'unknown' | null;
  last_connected_at: string | null;
  last_error: string | null;
  available_tools: {
    tools: Array<{name: string; description: string}>;
    count: number;
    updated_at: string;
  };
  created_at: string;
  updated_at: string;
  user_id: string | null;

  // 计算字段
  overall_status: MCPStatus;
  status_color: MCPStatusColor;
  status_text: string;
}

// 状态配置
export const MCP_STATUS_CONFIG: Record<
  MCPStatus,
  {
    color: MCPStatusColor;
    text: string;
    icon: string;
    tailwind: string;
  }
> = {
  disabled: {
    color: 'gray',
    text: '已禁用',
    icon: '⚪',
    tailwind: 'bg-gray-100 text-gray-600 border-gray-300',
  },
  connected: {
    color: 'green',
    text: '已连接',
    icon: '🟢',
    tailwind: 'bg-green-100 text-green-600 border-green-300',
  },
  failed: {
    color: 'red',
    text: '连接失败',
    icon: '🔴',
    tailwind: 'bg-red-100 text-red-600 border-red-300',
  },
  unknown: {
    color: 'yellow',
    text: '未测试',
    icon: '🟡',
    tailwind: 'bg-yellow-100 text-yellow-600 border-yellow-300',
  },
};
```

### React 组件示例

```typescript
// frontend/src/components/mcp/MCPServerCard.tsx
import React from 'react';
import { MCPServer, MCP_STATUS_CONFIG } from '@/types/mcp';

interface MCPServerCardProps {
  server: MCPServer;
  onTest: (id: string) => void;
  onToggle: (id: string, enabled: boolean) => void;
}

export const MCPServerCard: React.FC<MCPServerCardProps> = ({
  server,
  onTest,
  onToggle,
}) => {
  const status = MCP_STATUS_CONFIG[server.overall_status];

  return (
    <div className="mcp-server-card border rounded-lg p-4 hover:shadow-md transition">
      {/* 头部：名称 + 状态 */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold">{server.display_name}</h3>
        <div className={`px-3 py-1 rounded-full border text-sm ${status.tailwind}`}>
          <span className="mr-1">{status.icon}</span>
          {status.text}
        </div>
      </div>

      {/* 工具信息 */}
      <div className="space-y-2 text-sm text-gray-600 mb-3">
        <p>工具数量: {server.available_tools?.count || 0}</p>
        {server.last_connected_at && (
          <p>
            最后连接:{' '}
            {new Date(server.last_connected_at).toLocaleString('zh-CN')}
          </p>
        )}
      </div>

      {/* 错误信息 */}
      {server.last_error && (
        <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-600">
          ❌ {server.last_error}
        </div>
      )}

      {/* 操作按钮 */}
      <div className="flex gap-2">
        <button
          onClick={() => onTest(server.id)}
          disabled={!server.enabled}
          className="px-3 py-1.5 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          测试连接
        </button>
        <button
          onClick={() => onToggle(server.id, !server.enabled)}
          className={`px-3 py-1.5 rounded ${
            server.enabled
              ? 'bg-gray-200 hover:bg-gray-300'
              : 'bg-green-500 text-white hover:bg-green-600'
          }`}
        >
          {server.enabled ? '禁用' : '启用'}
        </button>
      </div>
    </div>
  );
};
```

### 状态徽章组件

```typescript
// frontend/src/components/mcp/MCPStatusBadge.tsx
import React from 'react';
import { MCPServer, MCP_STATUS_CONFIG } from '@/types/mcp';

interface MCPStatusBadgeProps {
  server: MCPServer;
  size?: 'sm' | 'md' | 'lg';
}

export const MCPStatusBadge: React.FC<MCPStatusBadgeProps> = ({
  server,
  size = 'md',
}) => {
  const status = MCP_STATUS_CONFIG[server.overall_status];

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-3 py-1 text-sm',
    lg: 'px-4 py-1.5 text-base',
  };

  return (
    <div
      className={`inline-flex items-center rounded-full border ${status.tailwind} ${sizeClasses[size]}`}
    >
      <span className="mr-1">{status.icon}</span>
      <span className="font-medium">{status.text}</span>
    </div>
  );
};
```

### 状态指示器组件（小圆点）

```typescript
// frontend/src/components/mcp/MCPStatusIndicator.tsx
import React from 'react';
import { MCPServer } from '@/types/mcp';

interface MCPStatusIndicatorProps {
  server: MCPServer;
  size?: 'sm' | 'md' | 'lg';
}

export const MCPStatusIndicator: React.FC<MCPStatusIndicatorProps> = ({
  server,
  size = 'md',
}) => {
  const colorMap = {
    gray: 'bg-gray-400',
    green: 'bg-green-500',
    red: 'bg-red-500',
    yellow: 'bg-yellow-500',
  };

  const sizeMap = {
    sm: 'w-2 h-2',
    md: 'w-3 h-3',
    lg: 'w-4 h-4',
  };

  const color = colorMap[server.status_color];

  return (
    <div className="relative inline-block">
      <div className={`${sizeMap[size]} ${color} rounded-full animate-pulse`} />
      <div
        className={`absolute top-0 left-0 ${sizeMap[size]} ${color} rounded-full opacity-75 animate-ping`}
      />
    </div>
  );
};
```

## 状态转换逻辑

### 前端状态计算

```typescript
// 如果前端需要自己计算（不依赖后端）
function calculateMCPStatus(
  enabled: boolean,
  connectionStatus: 'connected' | 'failed' | 'unknown' | null
): 'disabled' | 'connected' | 'failed' | 'unknown' {
  if (!enabled) return 'disabled';
  if (connectionStatus === 'connected') return 'connected';
  if (connectionStatus === 'failed') return 'failed';
  return 'unknown';
}

function getStatusColor(status: 'disabled' | 'connected' | 'failed' | 'unknown') {
  const colorMap = {
    disabled: 'gray',
    connected: 'green',
    failed: 'red',
    unknown: 'yellow',
  };
  return colorMap[status];
}

function getStatusText(status: 'disabled' | 'connected' | 'failed' | 'unknown') {
  const textMap = {
    disabled: '已禁用',
    connected: '已连接',
    failed: '连接失败',
    unknown: '未测试',
  };
  return textMap[status];
}
```

## 图标映射

### Emoji 图标

| 状态 | 图标 | 说明 |
|------|------|------|
| disabled | ⚪ | 灰色圆圈 |
| connected | 🟢 | 绿色圆圈 |
| failed | 🔴 | 红色圆圈 |
| unknown | 🟡 | 黄色圆圈 |

### SVG 图标（可选）

```typescript
export const MCP_STATUS_ICONS = {
  gray: (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
      <circle cx="10" cy="10" r="8" fill="#9ca3af" />
    </svg>
  ),
  green: (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
      <circle cx="10" cy="10" r="8" fill="#22c55e" />
      <path
        stroke="white"
        strokeWidth="2"
        d="M6 10l3 3 5-5"
        fill="none"
      />
    </svg>
  ),
  red: (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
      <circle cx="10" cy="10" r="8" fill="#ef4444" />
      <path
        stroke="white"
        strokeWidth="2"
        d="M7 7l6 6M13 7l-6 6"
        fill="none"
      />
    </svg>
  ),
  yellow: (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
      <circle cx="10" cy="10" r="8" fill="#eab308" />
      <text
        x="10"
        y="14"
        fontSize="8"
        textAnchor="middle"
        fill="white"
        fontWeight="bold"
      >
        ?
      </text>
    </svg>
  ),
};
```

## 使用建议

### 1. 列表视图

```
┌─────────────────────────────────────────────┐
│ 📁 文件系统         🟢 已连接   4个工具    │
│ 🐙 GitHub           🟡 未测试              │
│ 🗄️ PostgreSQL       🔴 连接失败            │
│ 🔍 Brave Search     🟢 已连接   1个工具    │
└─────────────────────────────────────────────┘
```

### 2. 卡片视图

```
┌─────────────────────────────────┐
│ 📁 文件系统        🟢 已连接   │
│                                 │
│ 工具: read_file, write_file... │
│ 最后连接: 2分钟前               │
│                                 │
│ [测试连接] [禁用]               │
└─────────────────────────────────┘
```

### 3. 表格视图

```
┌────────────┬──────────┬────────┬────────┐
│ 名称       │ 状态     │ 工具数 │ 操作   │
├────────────┼──────────┼────────┼────────┤
│ 文件系统   │ 🟢 已连接│ 4      │ [测试] │
│ GitHub     │ 🟡 未测试│ 0      │ [测试] │
│ PostgreSQL │ 🔴 失败  │ 0      │ [测试] │
└────────────┴──────────┴────────┴────────┘
```

## 注意事项

1. **禁用状态优先级最高**
   - `enabled=false` 时，无论 `connection_status` 是什么，都显示灰色

2. **未测试状态显示**
   - 新创建的服务器（`connection_status=null`）显示黄色
   - 未测试过的服务（`connection_status=unknown`）显示黄色

3. **测试连接后状态更新**
   - 成功：绿色 ✅
   - 失败：红色 ❌（显示 `last_error`）

4. **前端直接使用后端字段**
   - 使用 `overall_status`、`status_color`、`status_text`
   - 避免前端重复计算逻辑

## 总结

✅ **统一的状态系统**
- 后端计算 `overall_status`、`status_color`、`status_text`
- 前端直接使用，无需重复逻辑

✅ **明确的颜色规范**
- 灰色：禁用
- 绿色：已连接
- 红色：连接失败
- 黄色：未测试

✅ **完整的类型定义**
- TypeScript 类型
- React 组件示例
- 状态配置对象

✅ **用户友好**
- 中文状态文本
- Emoji 图标
- 清晰的颜色区分
