/**
 * 路由策略相关的纯函数工具
 *
 * 与后端 ``domains/gateway/domain/types.py::RoutingStrategy`` 字面量保持一致。
 * 当策略为 ``weighted-pick`` 时，Router 会按各 deployment 的 ``weight`` 做加权随机；
 * 因此 UI 也只在该策略下暴露权重编辑入口，避免误导用户配置无效字段。
 *
 * 与后端 ``domains/gateway/domain/policies/deployment_weight.py``
 * ``MIN_DEPLOYMENT_WEIGHT`` 保持一致。
 */
export const WEIGHTED_ROUTING_STRATEGY = 'weighted-pick' as const
export const MIN_DEPLOYMENT_WEIGHT = 1

export function isWeightedRoutingStrategy(strategy: string | null | undefined): boolean {
  return strategy === WEIGHTED_ROUTING_STRATEGY
}

/** 解析用户输入的 weight 文本；非法值返回 null（调用方自行回滚 draft）。 */
export function parseDeploymentWeight(raw: string): number | null {
  const n = Number.parseInt(raw.trim(), 10)
  return Number.isFinite(n) && n >= MIN_DEPLOYMENT_WEIGHT ? n : null
}
