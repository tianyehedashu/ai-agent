/**
 * MCP 管理相关类型定义
 */

/** MCP 环境类型 */
export type MCPEnvironmentType = 'dynamic_injected' | 'preinstalled' | 'custom_image'

/** MCP 作用域 */
export type MCPScope = 'system' | 'user'

/** MCP 服务器配置 */
export interface MCPServerConfig {
  id: string
  name: string
  display_name?: string
  url: string
  scope: MCPScope
  env_type: MCPEnvironmentType
  env_config: Record<string, unknown>
  enabled: boolean
  connection_status?: 'connected' | 'failed' | 'unknown' | null
  last_connected_at?: string | null
  last_error?: string | null
  available_tools?: Record<string, unknown>
  overall_status?: 'disabled' | 'connected' | 'failed' | 'unknown'
  status_color?: 'gray' | 'green' | 'red' | 'yellow'
  status_text?: string
  created_at: string
  updated_at: string
  user_id?: string
}

/** MCP 服务器列表响应 */
export interface MCPServersListResponse {
  system_servers: MCPServerConfig[]
  user_servers: MCPServerConfig[]
}

/** MCP 服务器实体配置 */
interface MCPServerEntityConfig {
  id?: string
  name: string
  display_name?: string
  url: string
  scope: MCPScope
  user_id?: string
  env_type: MCPEnvironmentType
  env_config: Record<string, unknown>
  enabled: boolean
}

/** MCP 模板 */
export interface MCPTemplate {
  id: string
  name: string
  display_name: string
  description: string
  category: string
  icon: string
  default_config: MCPServerEntityConfig
  required_fields: string[]
  optional_fields: string[]
  field_labels: Record<string, string>
  field_placeholders: Record<string, string>
  field_help_texts: Record<string, string>
}

/** 创建 MCP 服务器请求 */
export interface MCPServerCreateRequest {
  template_id?: string
  name: string
  display_name?: string
  url: string
  env_type: MCPEnvironmentType
  env_config: Record<string, unknown>
  enabled?: boolean
}

/** 更新 MCP 服务器请求 */
export interface MCPServerUpdateRequest {
  display_name?: string
  url?: string
  env_type?: MCPEnvironmentType
  env_config?: Record<string, unknown>
  enabled?: boolean
}

/** MCP 连接测试结果 */
export interface MCPTestResult {
  success: boolean
  message: string
  server_name: string
  server_url: string
  connection_status?: 'connected' | 'failed' | 'unknown' | null
  error_details?: string | null
  tools_count?: number
  tools_sample?: string[]
}

/** Session MCP 配置 */
export interface SessionMCPConfig {
  enabled_servers: string[]
}
