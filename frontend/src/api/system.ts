/**
 * System API
 */

import { apiClient } from './client'

export interface SimpleModelInfo {
  value: string
  label: string
  provider: string
}

export const systemApi = {
  /**
   * 获取可用模型列表（简单格式）
   */
  getModels(): Promise<SimpleModelInfo[]> {
    return apiClient.get<SimpleModelInfo[]>('/api/v1/system/models/simple')
  },
}
