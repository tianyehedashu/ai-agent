/**
 * Gateway 运行时能力开关（与部署 env 对齐，供控制台读取）
 */

import { apiClient } from '@/api/client'

import { teamGatewayPath } from './_base'

export interface GatewayFeatures {
  pii_guardrail_globally_enabled: boolean
}

export const featuresApi = {
  getFeatures(teamId: string): Promise<GatewayFeatures> {
    return apiClient.get<GatewayFeatures>(teamGatewayPath(teamId, '/features'))
  },
}
