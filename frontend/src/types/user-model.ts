/**
 * User Model Types - 用户模型类型
 */

export type ModelType = 'text' | 'image' | 'image_gen' | 'video'

export interface UserModelConfig {
  context_window?: number
  supports_vision?: boolean
  supports_tools?: boolean
  supports_reasoning?: boolean
  max_tokens?: number
  input_price?: number
  output_price?: number
  description?: string
}

/** 模型连通性测试三态：未测过 → null。 */
export type ModelTestStatus = 'success' | 'failed' | null

export interface UserModel {
  id: string
  user_id: string | null
  anonymous_user_id: string | null
  display_name: string
  provider: string
  model_id: string
  api_key_masked: string | null
  has_api_key: boolean
  api_base: string | null
  model_types: ModelType[]
  config: UserModelConfig | null
  is_active: boolean
  is_system: boolean
  /** 上次连通性测试结果，未测过为 null */
  last_test_status: ModelTestStatus
  /** 上次连通性测试时间（ISO 8601），未测过为 null */
  last_tested_at: string | null
  /** 上次失败/不支持时的说明；成功或未测过为 null */
  last_test_reason: string | null
  created_at: string | null
  updated_at: string | null
}

export interface SystemModel {
  id: string
  display_name: string
  provider: string
  model_id: string
  model_types: ModelType[]
  is_system: true
  config: UserModelConfig | null
}

/** 默认模型信息（用于展示「默认（模型名）」） */
export interface DefaultModelInfo {
  id: string
  display_name: string
}

export interface AvailableModelsResponse {
  system_models: SystemModel[]
  user_models: UserModel[]
  /** 文本能力默认模型（未选时展示） */
  default_for_text?: DefaultModelInfo
  /** 视觉能力默认模型（未选时展示） */
  default_for_vision?: DefaultModelInfo
  /** 图像生成默认模型（未选时展示） */
  default_for_image_gen?: DefaultModelInfo
}

export interface CreateUserModelBody {
  display_name: string
  provider: string
  model_id: string
  api_key?: string | null
  api_base?: string | null
  model_types?: ModelType[]
  config?: UserModelConfig | null
}

export interface UpdateUserModelBody {
  display_name?: string
  provider?: string
  model_id?: string
  api_key?: string | null
  api_base?: string | null
  model_types?: ModelType[]
  config?: UserModelConfig | null
  is_active?: boolean
}

export interface TestConnectionResult {
  success: boolean
  message: string
  model: string
  /** 与 ORM 落库字段同名，便于乐观更新 */
  status?: ModelTestStatus
  /** ISO 8601；与 last_tested_at 同语义 */
  tested_at?: string
  /** 与 ORM last_test_reason 一致；成功为 undefined/null */
  reason?: string | null
  response_preview?: string
}

export const MODEL_PROVIDERS = [
  { id: 'openai', name: 'OpenAI' },
  { id: 'anthropic', name: 'Anthropic' },
  { id: 'deepseek', name: 'DeepSeek' },
  { id: 'dashscope', name: '阿里云 (DashScope)' },
  { id: 'zhipuai', name: '智谱 AI' },
  { id: 'volcengine', name: '火山引擎' },
  { id: 'custom', name: '自定义' },
] as const

export const MODEL_TYPE_LABELS: Record<ModelType, string> = {
  text: '文本',
  image: '图片理解',
  image_gen: '图片生成',
  video: '视频',
}
