/**
 * Product Info API - 产品信息工作流 API
 */

import type {
  ProductInfoJob,
  ProductInfoJobListResponse,
  ProductInfoCapability,
  ProductInfoPromptTemplate,
  RunStepBody,
  OptimizePromptBody,
  OptimizePromptResponse,
  RunPipelineBody,
  RunPipelineResponse,
  ProductImageGenTask,
  ImageGenProvider,
} from '@/types/product-info'

import { apiClient } from './client'

const PREFIX = '/api/v1/product-info'

export const productInfoApi = {
  /** 创建任务 */
  async createJob(params?: { title?: string; session_id?: string }): Promise<ProductInfoJob> {
    const search = new URLSearchParams()
    if (params?.title !== undefined) {
      search.set('title', params.title)
    }
    if (params?.session_id !== undefined) {
      search.set('session_id', params.session_id)
    }
    const q = search.toString() ? `?${search.toString()}` : ''
    return apiClient.post<ProductInfoJob>(`${PREFIX}/jobs${q}`, {})
  },

  /** 任务列表 */
  async listJobs(params?: {
    skip?: number
    limit?: number
    status?: string
    session_id?: string
  }): Promise<ProductInfoJobListResponse> {
    const search: Record<string, string | number> = {}
    if (params?.skip !== undefined) search.skip = params.skip
    if (params?.limit !== undefined) search.limit = params.limit
    if (params?.status) search.status = params.status
    if (params?.session_id) search.session_id = params.session_id
    return apiClient.get<ProductInfoJobListResponse>(`${PREFIX}/jobs`, search)
  },

  /** 任务详情（含 steps） */
  async getJob(jobId: string): Promise<ProductInfoJob> {
    return apiClient.get<ProductInfoJob>(`${PREFIX}/jobs/${jobId}`)
  },

  /** 删除任务 */
  async deleteJob(jobId: string): Promise<void> {
    return apiClient.delete(`${PREFIX}/jobs/${jobId}`)
  },

  /** 执行某一步：渲染提示词后直接执行 */
  async runStep(jobId: string, body: RunStepBody): Promise<ProductInfoJob> {
    return apiClient.post<ProductInfoJob>(`${PREFIX}/jobs/${jobId}/steps`, body)
  },

  /** 可选：AI 优化提示词 */
  async optimizePrompt(jobId: string, body: OptimizePromptBody): Promise<OptimizePromptResponse> {
    return apiClient.post<OptimizePromptResponse>(`${PREFIX}/jobs/${jobId}/optimize-prompt`, body)
  },

  /** 能力列表 */
  async listCapabilities(): Promise<ProductInfoCapability[]> {
    return apiClient.get<ProductInfoCapability[]>(`${PREFIX}/capabilities`)
  },

  /** 默认提示词（恢复模板） */
  async getDefaultPrompt(
    capabilityId: string
  ): Promise<{ capability_id: string; content: string }> {
    return apiClient.get(`${PREFIX}/capabilities/${capabilityId}/default-prompt`)
  },

  /** 提示词可用占位符参数（用于插入 {{param}}） */
  async getCapabilityParams(
    capabilityId: string
  ): Promise<{ capability_id: string; params: { key: string; label: string }[] }> {
    return apiClient.get(`${PREFIX}/capabilities/${capabilityId}/params`)
  },

  /** 用户模板列表 */
  async listTemplates(
    capabilityId: string,
    params?: { skip?: number; limit?: number }
  ): Promise<{ items: ProductInfoPromptTemplate[]; total: number; skip: number; limit: number }> {
    const search: Record<string, string | number> = {}
    if (params?.skip !== undefined) search.skip = params.skip
    if (params?.limit !== undefined) search.limit = params.limit
    return apiClient.get(`${PREFIX}/capabilities/${capabilityId}/templates`, search)
  },

  /** 创建用户模板 */
  async createTemplate(
    capabilityId: string,
    body: { name: string; content?: string | null; prompts?: string[] | null }
  ): Promise<ProductInfoPromptTemplate> {
    return apiClient.post<ProductInfoPromptTemplate>(
      `${PREFIX}/capabilities/${capabilityId}/templates`,
      body
    )
  },

  /** 获取单条模板 */
  async getTemplate(templateId: string): Promise<ProductInfoPromptTemplate> {
    return apiClient.get<ProductInfoPromptTemplate>(`${PREFIX}/templates/${templateId}`)
  },

  /** 更新用户模板 */
  async updateTemplate(
    templateId: string,
    body: { name?: string | null; content?: string | null; prompts?: string[] | null }
  ): Promise<ProductInfoPromptTemplate> {
    return apiClient.patch<ProductInfoPromptTemplate>(`${PREFIX}/templates/${templateId}`, body)
  },

  /** 删除用户模板 */
  async deleteTemplate(templateId: string): Promise<void> {
    return apiClient.delete(`${PREFIX}/templates/${templateId}`)
  },

  /** 一键异步执行 */
  async run(body?: RunPipelineBody): Promise<RunPipelineResponse> {
    return apiClient.post<RunPipelineResponse>(`${PREFIX}/run`, body ?? {})
  },

  /** 上传图片（占位） */
  async upload(file: File): Promise<{ url: string; content_type: string; size_bytes: number }> {
    const form = new FormData()
    form.append('file', file)
    return apiClient.upload<{ url: string; content_type: string; size_bytes: number }>(
      `${PREFIX}/upload`,
      form
    )
  },

  /** 创建 8 图任务 */
  async createImageGenTask(body: {
    prompts?: Record<string, unknown>[]
    job_id?: string | null
    model_id?: string | null
    provider?: string | null
    size?: string | null
    reference_image_url?: string | null
    strength?: number | null
  }): Promise<ProductImageGenTask> {
    return apiClient.post<ProductImageGenTask>(`${PREFIX}/image-gen`, body)
  },

  /** 8 图任务列表 */
  async listImageGenTasks(params?: {
    skip?: number
    limit?: number
    jobId?: string
  }): Promise<{ items: ProductImageGenTask[]; total: number; skip: number; limit: number }> {
    const search: Record<string, string | number> = {}
    if (params?.skip !== undefined) search.skip = params.skip
    if (params?.limit !== undefined) search.limit = params.limit
    if (params?.jobId) search.job_id = params.jobId
    return apiClient.get(`${PREFIX}/image-gen`, search)
  },

  /** 8 图任务详情 */
  async getImageGenTask(taskId: string): Promise<ProductImageGenTask> {
    return apiClient.get<ProductImageGenTask>(`${PREFIX}/image-gen/${taskId}`)
  },

  /** 图像生成可用 provider 列表 */
  async getImageGenProviders(): Promise<{
    providers: ImageGenProvider[]
  }> {
    return apiClient.get(`${PREFIX}/image-gen/providers`)
  },
}
