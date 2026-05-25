/**
 * 用户图片上传 — 复用 listing-studio 存储端点（全站通用对象存储）
 */

import { apiV1Path } from '@/api/paths'

import { apiClient } from './client'

export interface UserImageUploadResult {
  url: string
  content_type: string
  size_bytes: number
}

const UPLOAD_PATH = apiV1Path('/listing-studio/upload')

export async function uploadUserImage(file: File): Promise<UserImageUploadResult> {
  const form = new FormData()
  form.append('file', file)
  return apiClient.upload<UserImageUploadResult>(UPLOAD_PATH, form)
}
