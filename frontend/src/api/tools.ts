/**
 * 内置工具 API
 *
 * 获取系统注册的内置工具列表（read_file, run_shell 等），供 Agent 配置选择使用。
 */

import { apiClient } from './client'

export interface ToolDefinition {
  name: string
  description: string
  parameters: Record<string, unknown>
  category: string
  requires_confirmation: boolean
}

export const toolsApi = {
  /**
   * 获取所有内置工具列表
   * @param category 可选，按类别筛选（如 code, file, search, external）
   */
  list(category?: string): Promise<ToolDefinition[]> {
    return apiClient.get<ToolDefinition[]>('/api/v1/tools/', category ? { category } : undefined)
  },

  /**
   * 获取单个工具详情
   */
  get(name: string): Promise<ToolDefinition> {
    return apiClient.get<ToolDefinition>(`/api/v1/tools/${encodeURIComponent(name)}`)
  },
}
