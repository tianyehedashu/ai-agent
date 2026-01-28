/**
 * MCP 管理 API 客户端
 */

import type {
  MCPServerConfig,
  MCPServerCreateRequest,
  MCPServerUpdateRequest,
  MCPServersListResponse,
  MCPTemplate,
  MCPTestResult,
  SessionMCPConfig,
  MCPToolInfo,
  MCPToolsListResponse,
} from '@/types/mcp'

import { apiClient } from './client'

export const mcpApi = {
  /**
   * 列出所有可用的 MCP 服务器模板
   */
  async listTemplates(): Promise<MCPTemplate[]> {
    return apiClient.get<MCPTemplate[]>('/api/v1/mcp/templates')
  },

  /**
   * 列出所有可用的 MCP 服务器
   */
  async listServers(): Promise<MCPServersListResponse> {
    return apiClient.get<MCPServersListResponse>('/api/v1/mcp/servers')
  },

  /**
   * 添加新的 MCP 服务器
   */
  async addServer(data: MCPServerCreateRequest): Promise<MCPServerConfig> {
    return apiClient.post<MCPServerConfig>('/api/v1/mcp/servers', data)
  },

  /**
   * 更新 MCP 服务器
   */
  async updateServer(id: string, data: MCPServerUpdateRequest): Promise<MCPServerConfig> {
    return apiClient.put<MCPServerConfig>(`/api/v1/mcp/servers/${id}`, data)
  },

  /**
   * 删除 MCP 服务器
   */
  async deleteServer(id: string): Promise<{ message: string }> {
    return apiClient.delete<{ message: string }>(`/api/v1/mcp/servers/${id}`)
  },

  /**
   * 切换服务器启用状态
   */
  async toggleServer(id: string, enabled: boolean): Promise<MCPServerConfig> {
    return apiClient.patch<MCPServerConfig>(
      `/api/v1/mcp/servers/${id}/toggle?enabled=${enabled ? 'true' : 'false'}`
    )
  },

  /**
   * 测试 MCP 服务器连接
   */
  async testConnection(id: string): Promise<MCPTestResult> {
    return apiClient.post<MCPTestResult>(`/api/v1/mcp/servers/${id}/test`)
  },

  /**
   * 获取 Session 的 MCP 配置
   * 注意：此API端点可能尚未在后端实现
   */
  async getSessionMCPConfig(sessionId: string): Promise<SessionMCPConfig> {
    return apiClient.get<SessionMCPConfig>(`/api/v1/sessions/${sessionId}/mcp-config`)
  },

  /**
   * 更新 Session 的 MCP 配置
   * 注意：此API端点可能尚未在后端实现
   */
  async updateSessionMCPConfig(
    sessionId: string,
    config: SessionMCPConfig
  ): Promise<SessionMCPConfig> {
    return apiClient.put<SessionMCPConfig>(`/api/v1/sessions/${sessionId}/mcp-config`, config)
  },

  /**
   * 获取服务器的工具列表
   */
  async getServerTools(id: string): Promise<MCPToolsListResponse> {
    return apiClient.get<MCPToolsListResponse>(`/api/v1/mcp/servers/${id}/tools`)
  },

  /**
   * 切换工具启用状态
   */
  async toggleToolEnabled(
    serverId: string,
    toolName: string,
    enabled: boolean
  ): Promise<MCPToolInfo> {
    return apiClient.put<MCPToolInfo>(
      `/api/v1/mcp/servers/${serverId}/tools/${encodeURIComponent(toolName)}/enabled`,
      { enabled }
    )
  },
}
