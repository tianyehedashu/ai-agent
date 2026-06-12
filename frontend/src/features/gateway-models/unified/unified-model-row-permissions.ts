/**
 * 统一模型列表行级权限（个人 / 团队 / 系统）。
 */

import type { GatewayModel } from '@/api/gateway/models'
import type { GatewayTeam } from '@/api/gateway/teams'
import {
  canDeleteGatewayModel,
  canManageGatewayModel,
  canResyncGatewayModelCapabilities,
  isConfigManagedSystemModel,
  isModelBatchSelectable,
} from '@/features/gateway-models/gateway-model-permissions'
import type { GatewayModelListItem } from '@/features/gateway-models/list/types'
import { isGatewayTeamWritable } from '@/features/gateway-teams/gateway-team-write-policy'

export interface UnifiedModelRowPermissionContext {
  viewerUserId: string | null
  isPlatformAdmin: boolean
  hasAuthSession: boolean
  teamById: ReadonlyMap<string, GatewayTeam>
}

function asGatewayModel(item: GatewayModelListItem): GatewayModel | null {
  if (item.scope === 'personal') return null
  return item.source as GatewayModel
}

function permissionContextForItem(
  item: GatewayModelListItem
): { preferSystem: boolean } | undefined {
  return item.scope === 'system' ? { preferSystem: true } : undefined
}

function teamCanWrite(item: GatewayModelListItem, ctx: UnifiedModelRowPermissionContext): boolean {
  const teamId = item.teamId
  if (!teamId) return false
  const team = ctx.teamById.get(teamId)
  if (!team) return false
  return isGatewayTeamWritable(team, ctx.isPlatformAdmin)
}

export function canManageUnifiedModelItem(
  item: GatewayModelListItem,
  ctx: UnifiedModelRowPermissionContext
): boolean {
  if (!ctx.hasAuthSession) return false
  if (item.scope === 'personal') return true
  const model = asGatewayModel(item)
  if (!model) return false
  return canManageGatewayModel(
    model,
    ctx.viewerUserId,
    teamCanWrite(item, ctx),
    ctx.isPlatformAdmin,
    permissionContextForItem(item)
  )
}

export function canDeleteUnifiedModelItem(
  item: GatewayModelListItem,
  ctx: UnifiedModelRowPermissionContext
): boolean {
  if (!ctx.hasAuthSession) return false
  if (item.scope === 'personal') return true
  const model = asGatewayModel(item)
  if (!model) return false
  return canDeleteGatewayModel(
    model,
    ctx.viewerUserId,
    teamCanWrite(item, ctx),
    ctx.isPlatformAdmin,
    permissionContextForItem(item)
  )
}

export function isConfigManagedUnifiedModelItem(item: GatewayModelListItem): boolean {
  if (item.scope !== 'system') return false
  const model = asGatewayModel(item)
  if (!model) return false
  return isConfigManagedSystemModel(model, { preferSystem: true })
}

export function canResyncUnifiedModelItem(
  item: GatewayModelListItem,
  ctx: UnifiedModelRowPermissionContext
): boolean {
  if (!ctx.hasAuthSession) return false
  if (item.scope === 'personal') return canManageUnifiedModelItem(item, ctx)
  const model = asGatewayModel(item)
  if (!model) return false
  return canResyncGatewayModelCapabilities(
    model,
    ctx.viewerUserId,
    teamCanWrite(item, ctx),
    ctx.isPlatformAdmin,
    permissionContextForItem(item)
  )
}

export function canBatchSelectUnifiedModelItem(
  item: GatewayModelListItem,
  ctx: UnifiedModelRowPermissionContext
): boolean {
  if (isConfigManagedUnifiedModelItem(item)) return false
  if (item.scope === 'personal') return canDeleteUnifiedModelItem(item, ctx)
  const model = asGatewayModel(item)
  if (!model) return false
  return isModelBatchSelectable(
    model,
    ctx.viewerUserId,
    teamCanWrite(item, ctx),
    ctx.isPlatformAdmin,
    permissionContextForItem(item)
  )
}
