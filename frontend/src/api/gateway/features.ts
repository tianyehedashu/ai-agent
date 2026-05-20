/**
 * AI Gateway · 运行时能力开关（与后端 GATEWAY_* env 对齐）
 */

import { apiClient } from '@/api/client'

import { GATEWAY_API_BASE } from './_base'

export interface GatewayFeatures {
  pii_guardrail_globally_enabled: boolean
}

export const featuresApi = {
  getFeatures(): Promise<GatewayFeatures> {
    return apiClient.get<GatewayFeatures>(`${GATEWAY_API_BASE}/features`)
  },
}
