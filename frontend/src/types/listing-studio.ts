/**
 * Listing Studio Types - Listing 创作工作流类型
 */

export type ListingStudioJobStatus = 'draft' | 'running' | 'completed' | 'failed' | 'partial'

export type ListingStudioStepStatus =
  | 'pending'
  | 'prompt_generating'
  | 'prompt_ready'
  | 'running'
  | 'completed'
  | 'failed'

export interface ListingStudioJobStep {
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
  status: ListingStudioStepStatus
  error_message: string | null
  created_at: string | null
  updated_at: string | null
}

export interface ListingStudioJob {
  id: string
  user_id: string | null
  session_id: string | null
  title: string | null
  status: ListingStudioJobStatus
  created_at: string | null
  updated_at: string | null
  steps?: ListingStudioJobStep[]
}

export interface ListingStudioJobListResponse {
  items: ListingStudioJob[]
  total: number
  skip: number
  limit: number
}

export interface ListingStudioCapability {
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

export interface ListingStudioCapabilitiesResponse {
  capabilities: ListingStudioCapability[]
  execution_layers: string[][]
}

export interface ListingStudioPromptTemplate {
  id: string
  user_id: string | null
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
  model_overrides?: Record<string, string> | null
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

/** Listing 创作页用户输入（草稿 persist） */
export interface ListingStudioInputs {
  product_link?: string
  competitor_link?: string
  product_name?: string
  keywords?: string
  image_urls?: string[]
}

export interface ProductImageGenTaskListResponse {
  items: ProductImageGenTask[]
  total: number
  skip: number
  limit: number
}
