/**
 * 用户 LLM 提供商配置类型
 */

export interface ProviderConfig {
  id: string
  provider: string
  /** 凭据别名；多账号时由后端返回 */
  name?: string
  api_base: string | null
  is_active: boolean
}

export interface ProviderConfigUpdateRequest {
  api_key: string
  api_base?: string | null
  is_active?: boolean
}

export interface ProviderTestResponse {
  success: boolean
}
