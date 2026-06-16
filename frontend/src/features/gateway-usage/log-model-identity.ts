/**
 * 调用日志 · 模型身份（与模型列表「调用名 / 显示名 / 上游」语义对齐）。
 *
 * SSOT 字段（落库）：
 * - route_name：客户端请求 model（调用名）
 * - deployment_gateway_model_id：Router 选中 GatewayModel.id（稳定主键）
 * - deployment_model_name：注册别名快照（GatewayModel.name）
 * - real_model：上游 canonical id（上游名）
 *
 * 显示名不落库，按 deployment_gateway_model_id 从模型目录解析。
 */

import type { GatewayLogItem } from '@/api/gateway/logs'
import type { GatewayModel } from '@/api/gateway/models'
import { gatewayModelDisplayName } from '@/features/gateway-models/list/gateway-model-display-name'

export type LogModelIdentitySource = Pick<
  GatewayLogItem,
  'route_name' | 'real_model' | 'deployment_gateway_model_id' | 'deployment_model_name'
>

export interface LogModelIdentity {
  /** Router 选中注册模型 id；详情跳转 / 目录解析主键 */
  gatewayModelId: string | null
  /** 客户端 model 参数（gateway_route_name） */
  invokeName: string | null
  /** tags.display_name（目录解析；与调用名相同时列表省略） */
  displayName: string | null
  /** 上游 real_model（canonical） */
  upstreamName: string | null
  /** 落库时 Router 注册别名快照；虚拟路由时可能与 invokeName 不同 */
  registrationName: string | null
}

export interface LogModelCatalogEntry {
  displayName: string | null
  registrationName: string
  upstreamName: string
}

export type LogModelCatalogIndex = ReadonlyMap<string, LogModelCatalogEntry>

function nonEmpty(value: string | null | undefined): string | null {
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

/** 从 callable 模型目录构建 id → 展示元数据索引（日志页与筛选共用）。 */
export function buildLogModelCatalogIndex(
  models: readonly Pick<GatewayModel, 'id' | 'name' | 'real_model' | 'tags'>[]
): LogModelCatalogIndex {
  const index = new Map<string, LogModelCatalogEntry>()
  for (const model of models) {
    const registrationName = model.name.trim()
    if (registrationName.length === 0) continue
    index.set(model.id, {
      displayName: gatewayModelDisplayName(model),
      registrationName,
      upstreamName: model.real_model.trim(),
    })
  }
  return index
}

/** 解析单条日志的模型三列；目录缺失时仅展示落库字段。 */
export function resolveLogModelIdentity(
  log: LogModelIdentitySource,
  catalog?: LogModelCatalogIndex
): LogModelIdentity {
  const gatewayModelId = nonEmpty(log.deployment_gateway_model_id)
  const invokeName = nonEmpty(log.route_name)
  const upstreamName = nonEmpty(log.real_model)
  const registrationName = nonEmpty(log.deployment_model_name)

  const fromCatalog = gatewayModelId && catalog ? catalog.get(gatewayModelId) : undefined

  let displayName = fromCatalog?.displayName ?? null
  if (displayName && invokeName && displayName === invokeName) {
    displayName = null
  }

  return {
    gatewayModelId,
    invokeName,
    displayName,
    upstreamName,
    registrationName,
  }
}

export function logModelIdentityTitle(identity: LogModelIdentity): string {
  return identity.invokeName ?? identity.registrationName ?? identity.upstreamName ?? '请求详情'
}
