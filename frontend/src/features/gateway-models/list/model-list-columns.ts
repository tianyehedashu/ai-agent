import { channelLabel } from '@/features/gateway-models/utils'

import { capabilityLabel, capabilityListLabel, modelTypeLabel } from '../constants'
import { resolveModelListDisplayLabel } from './gateway-model-display-name'

import type { GatewayModelListItem } from './types'

function uniqueModelTypeLabels(types: readonly string[]): string[] {
  const seen = new Set<string>()
  const labels: string[] = []
  for (const type of types) {
    const label = modelTypeLabel(type)
    if (seen.has(label)) continue
    seen.add(label)
    labels.push(label)
  }
  return labels
}

function joinCapabilityDisplayParts(capabilityPart: string, typeLabels: readonly string[]): string {
  if (typeLabels.length === 0) return capabilityPart
  return [capabilityPart, ...typeLabels].join(' · ')
}

/** API / 路由调用时使用的模型名 */
export function clientInvokeModelName(item: GatewayModelListItem): string {
  if (item.scope === 'personal') {
    return item.routeName ?? item.title
  }
  return item.routeVirtualModel ?? item.title
}

/** 人类可读展示名；个人模型在与调用路由相同时省略，避免与调用名列重复 */
export function listDisplayName(item: GatewayModelListItem): string | null {
  const label = resolveModelListDisplayLabel(item)
  if (!label) return null
  if (item.scope === 'personal') {
    const invoke = clientInvokeModelName(item)
    if (label === invoke) return null
  }
  return label
}

export function upstreamChannelLabel(item: GatewayModelListItem): string {
  return channelLabel(item.provider)
}

export function listCapabilityLabel(item: GatewayModelListItem): string {
  const cap = capabilityListLabel(item.capability)
  const types = uniqueModelTypeLabels(item.modelTypes)
  return joinCapabilityDisplayParts(cap, types)
}

/** Tooltip / 详情用完整能力文案 */
export function listCapabilityFullLabel(item: GatewayModelListItem): string {
  const cap = capabilityLabel(item.capability)
  const types = uniqueModelTypeLabels(item.modelTypes)
  return joinCapabilityDisplayParts(cap, types)
}

export function listCredentialName(item: GatewayModelListItem): string | null {
  return item.credentialName?.trim() ?? null
}
