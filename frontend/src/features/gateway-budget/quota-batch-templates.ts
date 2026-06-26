/**
 * 配额批量设置模板预设：一键填充常用限额组合。
 */

import type { QuotaBatchFormValues } from './use-quota-center'

export interface QuotaTemplate {
  label: string
  description: string
  patch: Partial<
    Pick<
      QuotaBatchFormValues,
      'period' | 'limit_usd' | 'limit_tokens' | 'limit_requests' | 'limit_images'
    >
  >
}

export const QUOTA_TEMPLATES: QuotaTemplate[] = [
  {
    label: '轻度使用',
    description: '每日 $10',
    patch: {
      period: 'daily',
      limit_usd: '10',
      limit_tokens: '',
      limit_requests: '',
      limit_images: '',
    },
  },
  {
    label: '标准使用',
    description: '每月 $100',
    patch: {
      period: 'monthly',
      limit_usd: '100',
      limit_tokens: '',
      limit_requests: '',
      limit_images: '',
    },
  },
  {
    label: '高用量',
    description: '每月 $500',
    patch: {
      period: 'monthly',
      limit_usd: '500',
      limit_tokens: '',
      limit_requests: '',
      limit_images: '',
    },
  },
  {
    label: 'Token 限制',
    description: '每月 1M Token',
    patch: {
      period: 'monthly',
      limit_usd: '',
      limit_tokens: '1000000',
      limit_requests: '',
      limit_images: '',
    },
  },
  {
    label: '请求限制',
    description: '每日 1,000 次',
    patch: {
      period: 'daily',
      limit_usd: '',
      limit_tokens: '',
      limit_requests: '1000',
      limit_images: '',
    },
  },
  {
    label: '图像限制',
    description: '每日 50 张图',
    patch: {
      period: 'daily',
      limit_usd: '',
      limit_tokens: '',
      limit_requests: '',
      limit_images: '50',
    },
  },
  {
    label: '严格限额',
    description: '每日 $1 + 100 次',
    patch: {
      period: 'daily',
      limit_usd: '1',
      limit_tokens: '',
      limit_requests: '100',
      limit_images: '',
    },
  },
]

/** 将模板 patch 应用到当前表单值，保留主体/层级/模型等已有选择。 */
export function applyQuotaTemplate(
  values: QuotaBatchFormValues,
  template: QuotaTemplate
): QuotaBatchFormValues {
  return {
    ...values,
    ...template.patch,
  }
}
