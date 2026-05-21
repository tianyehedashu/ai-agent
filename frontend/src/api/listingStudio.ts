/**
 * Listing Studio API - Listing 创作工作流 API
 */

import { apiV1Path } from '@/api/paths'
import type {
  ListingStudioJob,
  ListingStudioJobListResponse,
  ListingStudioCapabilitiesResponse,
  ListingStudioPromptTemplate,
  RunStepBody,
  OptimizePromptBody,
  OptimizePromptResponse,
  RunPipelineBody,
  RunPipelineResponse,
  ProductImageGenTask,
  ProductImageGenTaskListResponse,
  ImageGenProvider,
} from '@/types/listing-studio'

import { apiClient } from './client'

const PREFIX = apiV1Path('/listing-studio')

export const listingStudioApi = {
  async createJob(params?: { title?: string; session_id?: string }): Promise<ListingStudioJob> {
    const search = new URLSearchParams()
    if (params?.title !== undefined) {
      search.set('title', params.title)
    }
    if (params?.session_id !== undefined) {
      search.set('session_id', params.session_id)
    }
    const q = search.toString() ? `?${search.toString()}` : ''
    return apiClient.post<ListingStudioJob>(`${PREFIX}/jobs${q}`, {})
  },

  async listJobs(params?: {
    skip?: number
    limit?: number
    status?: string
    session_id?: string
  }): Promise<ListingStudioJobListResponse> {
    const search: Record<string, string | number> = {}
    if (params?.skip !== undefined) search.skip = params.skip
    if (params?.limit !== undefined) search.limit = params.limit
    if (params?.status) search.status = params.status
    if (params?.session_id) search.session_id = params.session_id
    return apiClient.get<ListingStudioJobListResponse>(`${PREFIX}/jobs`, search)
  },

  async getJob(jobId: string): Promise<ListingStudioJob> {
    return apiClient.get<ListingStudioJob>(`${PREFIX}/jobs/${jobId}`)
  },

  async deleteJob(jobId: string): Promise<void> {
    return apiClient.delete(`${PREFIX}/jobs/${jobId}`)
  },

  async runStep(jobId: string, body: RunStepBody): Promise<ListingStudioJob> {
    return apiClient.post<ListingStudioJob>(`${PREFIX}/jobs/${jobId}/steps`, body)
  },

  async optimizePrompt(jobId: string, body: OptimizePromptBody): Promise<OptimizePromptResponse> {
    return apiClient.post<OptimizePromptResponse>(`${PREFIX}/jobs/${jobId}/optimize-prompt`, body)
  },

  async listCapabilities(): Promise<ListingStudioCapabilitiesResponse> {
    return apiClient.get<ListingStudioCapabilitiesResponse>(`${PREFIX}/capabilities`)
  },

  async getDefaultPrompt(
    capabilityId: string
  ): Promise<{ capability_id: string; content: string }> {
    return apiClient.get(`${PREFIX}/capabilities/${capabilityId}/default-prompt`)
  },

  async getCapabilityParams(
    capabilityId: string
  ): Promise<{ capability_id: string; params: { key: string; label: string }[] }> {
    return apiClient.get(`${PREFIX}/capabilities/${capabilityId}/params`)
  },

  async listTemplates(
    capabilityId: string,
    params?: { skip?: number; limit?: number }
  ): Promise<{ items: ListingStudioPromptTemplate[]; total: number; skip: number; limit: number }> {
    const search: Record<string, string | number> = {}
    if (params?.skip !== undefined) search.skip = params.skip
    if (params?.limit !== undefined) search.limit = params.limit
    return apiClient.get(`${PREFIX}/capabilities/${capabilityId}/templates`, search)
  },

  async createTemplate(
    capabilityId: string,
    body: { name: string; content?: string | null; prompts?: string[] | null }
  ): Promise<ListingStudioPromptTemplate> {
    return apiClient.post<ListingStudioPromptTemplate>(
      `${PREFIX}/capabilities/${capabilityId}/templates`,
      body
    )
  },

  async getTemplate(templateId: string): Promise<ListingStudioPromptTemplate> {
    return apiClient.get<ListingStudioPromptTemplate>(`${PREFIX}/templates/${templateId}`)
  },

  async updateTemplate(
    templateId: string,
    body: { name?: string | null; content?: string | null; prompts?: string[] | null }
  ): Promise<ListingStudioPromptTemplate> {
    return apiClient.patch<ListingStudioPromptTemplate>(`${PREFIX}/templates/${templateId}`, body)
  },

  async deleteTemplate(templateId: string): Promise<void> {
    return apiClient.delete(`${PREFIX}/templates/${templateId}`)
  },

  async run(body?: RunPipelineBody): Promise<RunPipelineResponse> {
    return apiClient.post<RunPipelineResponse>(`${PREFIX}/run`, body ?? {})
  },

  async upload(file: File): Promise<{ url: string; content_type: string; size_bytes: number }> {
    const form = new FormData()
    form.append('file', file)
    return apiClient.upload<{ url: string; content_type: string; size_bytes: number }>(
      `${PREFIX}/upload`,
      form
    )
  },

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

  async listImageGenTasks(params?: {
    skip?: number
    limit?: number
    jobId?: string
  }): Promise<ProductImageGenTaskListResponse> {
    const search: Record<string, string | number> = {}
    if (params?.skip !== undefined) search.skip = params.skip
    if (params?.limit !== undefined) search.limit = params.limit
    if (params?.jobId) search.job_id = params.jobId
    return apiClient.get(`${PREFIX}/image-gen`, search)
  },

  async getImageGenTask(taskId: string): Promise<ProductImageGenTask> {
    return apiClient.get<ProductImageGenTask>(`${PREFIX}/image-gen/${taskId}`)
  },

  async getImageGenProviders(): Promise<{ providers: ImageGenProvider[] }> {
    return apiClient.get(`${PREFIX}/image-gen/providers`)
  },
}
