/**
 * Product Info Types - 产品信息工作流类型
 */

export type ProductInfoJobStatus = 'draft' | 'running' | 'completed' | 'failed' | 'partial'

export type ProductInfoStepStatus =
  | 'pending'
  | 'prompt_generating'
  | 'prompt_ready'
  | 'running'
  | 'completed'
  | 'failed'

export interface ProductInfoJobStep {
  id: string
  job_id: string
  sort_order: number
  capability_id: string
  input_snapshot: Record<string, unknown> | null
  output_snapshot: Record<string, unknown> | null
  meta_prompt: string | null
  generated_prompt: string | null
  prompt_used: string | null
  prompt_template_id: string | null
  status: ProductInfoStepStatus
  error_message: string | null
  created_at: string | null
  updated_at: string | null
}

export interface ProductInfoJob {
  id: string
  user_id: string | null
  anonymous_user_id: string | null
  session_id: string | null
  title: string | null
  status: ProductInfoJobStatus
  created_at: string | null
  updated_at: string | null
  steps?: ProductInfoJobStep[]
}

export interface ProductInfoJobListResponse {
  items: ProductInfoJob[]
  total: number
  skip: number
  limit: number
}

export interface ProductInfoCapability {
  id: string
  name: string
  sort_order?: number
  model_type?: 'text' | 'image'
  output_key?: string
  dependencies?: string[]
  input_fields?: string[]
  meta_prompt_params?: { key: string; label: string }[]
  required_features?: string[]
}

export interface ProductInfoPromptTemplate {
  id: string
  user_id: string | null
  anonymous_user_id: string | null
  capability_id: string
  name: string
  content: string | null
  prompts: string[] | null
  created_at: string | null
  updated_at: string | null
}

export interface RunStepBody {
  capability_id: string
  user_input: Record<string, unknown>
  model_id?: string | null
  meta_prompt?: string | null
  generated_prompt?: string | null
  prompt_template_id?: string | null
  /** 执行阶段：generate_prompt | execute | full */
  phase?: 'generate_prompt' | 'execute' | 'full'
}

export interface OptimizePromptBody {
  capability_id: string
  user_input: Record<string, unknown>
  meta_prompt?: string | null
  model_id?: string | null
}

export interface OptimizePromptResponse {
  capability_id: string
  optimized_prompt: string
}

export interface RunPipelineBody {
  inputs?: Record<string, unknown>
  steps?: string[] | null
  session_id?: string | null
}

export interface RunPipelineResponse {
  job_id: string
  status: string
  message: string
  poll_url: string
}

export interface ProductImageGenTask {
  id: string
  job_id?: string | null
  status: string
  prompts: Record<string, unknown>[]
  result_images: { slot: number; url: string; error?: string; skipped?: boolean }[] | null
  error_message: string | null
  created_at: string | null
  updated_at?: string | null
}

export interface ImageGenProvider {
  id: string
  name: string
  default_size: string
  sizes: string[]
  supports_reference_image: boolean
}
