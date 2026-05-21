/**
 * System API
 */

import { apiV1Path } from '@/api/paths'

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
    return apiClient.get<SimpleModelInfo[]>(apiV1Path('/system/models/simple'))
  },
}
