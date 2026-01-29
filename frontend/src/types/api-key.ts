/**
 * API Key Management Types
 *
 * API Key 管理相关的类型定义
 */

// =============================================================================
// API Key Status
// =============================================================================

export type ApiKeyStatus = 'active' | 'expired' | 'revoked'

// =============================================================================
// API Key Scope
// =============================================================================

export type ApiKeyScope =
  | 'agent:read'
  | 'agent:update'
  | 'agent:execute'
  | 'session:read'
  | 'session:create'
  | 'session:delete'
  | 'memory:read'
  | 'memory:write'
  | 'workflow:read'
  | 'workflow:update'
  | 'system:read'
  // MCP 服务器访问
  | 'mcp:llm-server'
  | 'mcp:filesystem-server'
  | 'mcp:memory-server'
  | 'mcp:workflow-server'
  | 'mcp:custom-server'
  | 'mcp:all'

// =============================================================================
// Scope Groups (预设作用域分组)
// =============================================================================

export const API_KEY_SCOPE_GROUPS: Record<string, ApiKeyScope[]> = {
  read_only: [
    'agent:read',
    'session:read',
    'memory:read',
    'workflow:read',
    'system:read',
  ],
  full_access: [
    'agent:read',
    'agent:update',
    'agent:execute',
    'session:read',
    'session:create',
    'session:delete',
    'memory:read',
    'memory:write',
    'workflow:read',
    'workflow:update',
    'system:read',
  ],
  agent_only: [
    'agent:read',
    'agent:execute',
    'session:read',
    'session:create',
  ],
  // MCP 相关分组
  mcp_llm_only: ['mcp:llm-server'],
  mcp_all: [
    'mcp:llm-server',
    'mcp:filesystem-server',
    'mcp:memory-server',
    'mcp:workflow-server',
    'mcp:custom-server',
  ],
  mcp_full: ['mcp:all'],
}

// =============================================================================
// API Key Types
// =============================================================================

export interface ApiKey {
  id: string
  name: string
  description?: string
  scopes: ApiKeyScope[]
  expires_at: string
  is_active: boolean
  status: ApiKeyStatus
  last_used_at?: string
  usage_count: number
  created_at: string
  masked_key: string
}

export interface ApiKeyCreateRequest {
  name: string
  description?: string
  scopes: ApiKeyScope[]
  expires_in_days: number
}

export interface ApiKeyUpdateRequest {
  name?: string
  description?: string
  scopes?: ApiKeyScope[]
  extend_expiry_days?: number
  is_active?: boolean
}

export interface ApiKeyCreatedResponse {
  api_key: ApiKey
  plain_key: string
  warning: string
}

// =============================================================================
// API Key Usage Log Types
// =============================================================================

export interface ApiKeyUsageLog {
  id: string
  endpoint: string
  method: string
  ip_address?: string
  user_agent?: string
  status_code: number
  response_time_ms?: number
  created_at: string
}

// =============================================================================
// Scope Display Info
// =============================================================================

export const SCOPE_DISPLAY_INFO: Record<
  ApiKeyScope,
  { label: string; description: string; category: string }
> = {
  'agent:read': {
    label: '读取 Agent',
    description: '查看 Agent 列表和详情',
    category: 'Agent',
  },
  'agent:update': {
    label: '管理 Agent',
    description: '创建、编辑和删除 Agent',
    category: 'Agent',
  },
  'agent:execute': {
    label: '执行 Agent',
    description: '运行 Agent 对话',
    category: 'Agent',
  },
  'session:read': {
    label: '读取会话',
    description: '查看会话列表和详情',
    category: 'Session',
  },
  'session:create': {
    label: '创建会话',
    description: '创建新的对话会话',
    category: 'Session',
  },
  'session:delete': {
    label: '删除会话',
    description: '删除对话会话',
    category: 'Session',
  },
  'memory:read': {
    label: '读取记忆',
    description: '查看记忆内容',
    category: 'Memory',
  },
  'memory:write': {
    label: '管理记忆',
    description: '创建和编辑记忆',
    category: 'Memory',
  },
  'workflow:read': {
    label: '读取工作流',
    description: '查看工作流列表和详情',
    category: 'Workflow',
  },
  'workflow:update': {
    label: '管理工作流',
    description: '创建、编辑和删除工作流',
    category: 'Workflow',
  },
  'system:read': {
    label: '系统信息',
    description: '访问系统信息',
    category: 'System',
  },
  'mcp:llm-server': {
    label: 'MCP LLM 服务器',
    description: '访问 MCP LLM 服务器',
    category: 'MCP',
  },
  'mcp:filesystem-server': {
    label: 'MCP 文件系统服务器',
    description: '访问 MCP 文件系统服务器',
    category: 'MCP',
  },
  'mcp:memory-server': {
    label: 'MCP 记忆服务器',
    description: '访问 MCP 记忆系统服务器',
    category: 'MCP',
  },
  'mcp:workflow-server': {
    label: 'MCP 工作流服务器',
    description: '访问 MCP 工作流服务器',
    category: 'MCP',
  },
  'mcp:custom-server': {
    label: 'MCP 自定义服务器',
    description: '访问 MCP 自定义服务器',
    category: 'MCP',
  },
  'mcp:all': {
    label: '所有 MCP 服务器',
    description: '访问所有 MCP 服务器',
    category: 'MCP',
  },
}

// =============================================================================
// Expiration Options
// =============================================================================

export const EXPIRATION_OPTIONS = [
  { value: 30, label: '30 天' },
  { value: 90, label: '90 天' },
  { value: 180, label: '180 天' },
  { value: 365, label: '1 年' },
] as const

export type ExpirationValue = (typeof EXPIRATION_OPTIONS)[number]['value']

// =============================================================================
// Utility Functions
// =============================================================================

export function getScopeCategory(scopes: ApiKeyScope[]): string[] {
  const categories = new Set<string>()
  for (const scope of scopes) {
    categories.add(SCOPE_DISPLAY_INFO[scope].category)
  }
  return Array.from(categories)
}

export function formatScope(scope: ApiKeyScope): string {
  return SCOPE_DISPLAY_INFO[scope].label
}

// 注意：formatRelativeTime 已移至 @/lib/utils，请从该模块导入

export function getDaysUntilExpiry(expiresAt: string): number {
  const expiryDate = new Date(expiresAt)
  const now = new Date()
  const diffMs = expiryDate.getTime() - now.getTime()
  return Math.max(0, Math.floor(diffMs / (1000 * 60 * 60 * 24)))
}

export function getStatusColor(status: ApiKeyStatus): string {
  switch (status) {
    case 'active':
      return 'text-green-600'
    case 'expired':
      return 'text-yellow-600'
    case 'revoked':
      return 'text-red-600'
    default:
      return 'text-gray-600'
  }
}

export function getStatusBadgeVariant(status: ApiKeyStatus): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'active':
      return 'default'
    case 'expired':
      return 'secondary'
    case 'revoked':
      return 'destructive'
    default:
      return 'outline'
  }
}

export function getStatusLabel(status: ApiKeyStatus): string {
  switch (status) {
    case 'active':
      return '活跃'
    case 'expired':
      return '已过期'
    case 'revoked':
      return '已撤销'
    default:
      return '未知'
  }
}
