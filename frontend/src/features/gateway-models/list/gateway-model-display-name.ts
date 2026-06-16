/**
 * 模型人类可读展示名（与后端 proxy_model_list_reads / personal_models 对齐）。
 */

import type { GatewayModel } from '@/api/gateway/models'
import type { PersonalGatewayModel } from '@/api/gateway/my-models'

import type { GatewayModelListItem } from './types'

function tagDisplayName(tags: Record<string, unknown> | null | undefined): string | null {
  const raw = tags?.display_name
  if (typeof raw !== 'string') return null
  const trimmed = raw.trim()
  return trimmed.length > 0 ? trimmed : null
}

/** 团队 / 系统注册行：tags.display_name，缺省回退注册别名 name（与后端 selector 一致） */
export function gatewayModelDisplayName(model: Pick<GatewayModel, 'name' | 'tags'>): string | null {
  const fromTags = tagDisplayName(model.tags)
  if (fromTags) return fromTags
  const name = model.name.trim()
  return name.length > 0 ? name : null
}

/** 个人模型：API display_name 字段 */
export function personalModelDisplayName(model: PersonalGatewayModel): string | null {
  const raw = model.display_name
  if (typeof raw !== 'string') return null
  const trimmed = raw.trim()
  return trimmed.length > 0 ? trimmed : null
}

/** 列表 ViewModel 原始展示名（未与调用名去重） */
export function resolveModelListDisplayLabel(item: GatewayModelListItem): string | null {
  if (item.displayName) {
    const trimmed = item.displayName.trim()
    return trimmed.length > 0 ? trimmed : null
  }
  if (item.scope === 'personal' && 'display_name' in item.source) {
    return personalModelDisplayName(item.source)
  }
  if ('real_model' in item.source) {
    return gatewayModelDisplayName(item.source)
  }
  return null
}

/** 面包屑 / 标签等：展示名优先，否则注册别名 */
export function gatewayModelLabel(model: GatewayModel): string {
  return gatewayModelDisplayName(model) ?? model.name
}
