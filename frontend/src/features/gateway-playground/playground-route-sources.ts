/**
 * Playground / 调用指南：团队自有路由 + 共享进团队的路由合并。
 */

import type { GatewayRoute, SharedRoute } from '@/api/gateway/routes'

/** filterPlaygroundRouteCandidates 所需的最小路由行 */
export interface PlaygroundRouteRow {
  enabled: boolean
  virtual_model: string
  primary_models: string[]
  /** 个人路由经 grant 共享进消费团队 */
  isSharedRoute?: boolean
  ownerDisplay?: string | null
}

export interface PlaygroundRouteFetchPolicy {
  includeOwnedRoutes: boolean
  includeSharedRoutes: boolean
}

export function resolvePlaygroundRouteFetchPolicy(params: {
  fetchRoutes: boolean
  proxyTeamId: string | null
  isPersonalProxyTeam: boolean
  credentialId: string
  isPersonalCredential: boolean
  usingProxyModelList: boolean
}): PlaygroundRouteFetchPolicy {
  const {
    fetchRoutes,
    proxyTeamId,
    isPersonalProxyTeam,
    credentialId,
    isPersonalCredential,
    usingProxyModelList,
  } = params
  const credentialBlocksRoutes = Boolean(credentialId && isPersonalCredential)
  const baseEnabled = fetchRoutes && Boolean(proxyTeamId) && !credentialBlocksRoutes
  return {
    includeOwnedRoutes: baseEnabled && !usingProxyModelList,
    includeSharedRoutes: baseEnabled && !isPersonalProxyTeam,
  }
}

export function sharedRouteToPlaygroundRow(shared: SharedRoute): PlaygroundRouteRow {
  return {
    enabled: shared.enabled ?? true,
    virtual_model: shared.exposed_alias,
    primary_models: shared.primary_models ?? [],
    isSharedRoute: true,
    ownerDisplay: shared.owner_display ?? null,
  }
}

export function ownedRouteToPlaygroundRow(route: GatewayRoute): PlaygroundRouteRow {
  return {
    enabled: route.enabled,
    virtual_model: route.virtual_model,
    primary_models: route.primary_models,
    isSharedRoute: false,
  }
}

/** 合并团队路由与共享路由；同名时保留团队自有路由。 */
export function mergePlaygroundRouteRows(
  ownedRoutes: readonly GatewayRoute[] | undefined,
  sharedRoutes: readonly SharedRoute[] | undefined
): PlaygroundRouteRow[] {
  const ownedNames = new Set((ownedRoutes ?? []).map((route) => route.virtual_model))
  const merged: PlaygroundRouteRow[] = (ownedRoutes ?? []).map(ownedRouteToPlaygroundRow)
  for (const shared of sharedRoutes ?? []) {
    if (ownedNames.has(shared.exposed_alias)) continue
    merged.push(sharedRouteToPlaygroundRow(shared))
  }
  return merged
}
