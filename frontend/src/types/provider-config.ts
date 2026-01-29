/**
 * 用户 LLM 提供商配置类型
 */

export interface ProviderConfig {
  id: string
  provider: string
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

export const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI (GPT)',
  anthropic: 'Anthropic (Claude)',
  dashscope: '阿里云 DashScope (通义千问)',
  zhipuai: '智谱 AI (GLM)',
  deepseek: 'DeepSeek',
  volcengine: '火山引擎 (豆包)',
}
