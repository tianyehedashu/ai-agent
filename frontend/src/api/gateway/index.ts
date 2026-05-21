/**
 * AI Gateway API Client（聚合）
 *
 * 统一封装 /api/v1/gateway/* 管理端点。
 * 团队资源通过 URL 路径 `/teams/{teamId}/*` 显式选团队（见 `teamGatewayPath`）。
 *
 * 文件按资源拆分，详见同目录下：
 * - teams / keys / credentials / models / my-models / routes
 * - budgets / logs / alerts / entitlements / pricing
 *
 * 公共出口（保持与历史 `@/api/gateway` 调用方兼容）：
 * - `gatewayApi`：所有资源 API 的合并对象
 * - 各资源类型直接 re-export
 */

import { alertsApi } from './alerts'
import { budgetsApi } from './budgets'
import { credentialsApi } from './credentials'
import { entitlementsApi } from './entitlements'
import { featuresApi } from './features'
import { keysApi } from './keys'
import { logsApi } from './logs'
import { modelsApi } from './models'
import { myModelsApi } from './my-models'
import { pricingApi } from './pricing'
import { routesApi } from './routes'
import { teamsApi } from './teams'

// ---------- 常量 / 共享类型 ----------

export { GATEWAY_API_BASE, GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES } from './_base'

// ---------- 资源类型 re-export ----------

export type { GatewayTeam, TeamMember } from './teams'

export type { GatewayFeatures } from './features'

export type {
  VirtualKey,
  VirtualKeyCreated,
  VirtualKeyBatchRevokeReason,
  VirtualKeyBatchRevokeFailure,
  VirtualKeyBatchRevokeResult,
  VirtualKeyCreateBody,
} from './keys'

export type {
  CredentialSummary,
  ProviderCredential,
  ProviderCredentialCreateBody,
  MyCredentialCreateBody,
  GatewayCredentialUpdateBody,
  CredentialProbeSupport,
  CredentialProbeUpstream,
  CredentialUpstreamItem,
  CredentialProbeResult,
  PersonalModelBatchImportBody,
  PersonalModelBatchImportCreatedItem,
  PersonalModelBatchImportResponse,
  BatchImportFailureItem,
  TeamGatewayModelBatchImportItem,
  TeamGatewayModelBatchImportBody,
  TeamGatewayModelBatchImportCreatedItem,
  TeamGatewayModelBatchImportResponse,
} from './credentials'

export type {
  GatewayModel,
  GatewayModelRouteUsageSlice,
  GatewayModelRouteUsageItem,
  GatewayModelUsageSummary,
  PlatformCredentialStat,
  GatewayModelTestResult,
  GatewayModelPreset,
  GatewayModelCreateBody,
  GatewayModelUpdateBody,
} from './models'

export type {
  PersonalGatewayModel,
  PersonalGatewayModelCreateBody,
  PersonalGatewayModelUpdateBody,
} from './my-models'

export type { GatewayRoute, GatewayRouteCreateBody, GatewayRouteUpdateBody } from './routes'

export type { GatewayBudget, BudgetUpsertBody } from './budgets'

export type {
  GatewayUsageAggregation,
  GatewayLogItem,
  GatewayLogDetail,
  GatewayLogsQuery,
  GatewayLogsPage,
  DashboardSummary,
} from './logs'

export type { AlertRule, AlertRuleCreateBody } from './alerts'

export type {
  PlanResetStrategy,
  PlanQuotaInput,
  EntitlementPlanQuotaInput,
  PlanQuota,
  EntitlementPlanQuota,
  ProviderPlan,
  ProviderPlanCreateBody,
  ProviderPlanUpdateBody,
  ProviderPlanCost,
  EntitlementPlan,
  EntitlementPlanCreateBody,
  EntitlementPlanUpdateBody,
  EntitlementUsage,
  MarginGroupItem,
  MarginGroupBy,
  MarginSummary,
} from './entitlements'

export type {
  FxRateInfo,
  UpstreamPricingRow,
  UpstreamPricingUpsertBody,
  DownstreamPricingRow,
  DownstreamPricingUpsertBody,
  MyPriceRow,
  UpstreamPricingAuditResult,
  LitellmUpstreamSyncResult,
  EffectiveProvider,
  LitellmUpstreamSyncBody,
  PricingEstimateBody,
  PricingEstimateResult,
  PricingReconciliationResult,
} from './pricing'

// ---------- 资源 API 命名空间 re-export（按资源调用更显意图） ----------

export {
  teamsApi,
  featuresApi,
  keysApi,
  credentialsApi,
  modelsApi,
  myModelsApi,
  routesApi,
  budgetsApi,
  logsApi,
  alertsApi,
  entitlementsApi,
  pricingApi,
}

// ---------- 聚合：统一对外的 gatewayApi ----------

/**
 * 历史调用方使用 `gatewayApi.xxx()` 形式，这里把所有资源合并为一个对象。
 *
 * 新代码建议优先使用具体的命名空间（如 `keysApi.listKeys()`），更便于摇树与代码定位。
 */
export const gatewayApi = {
  ...teamsApi,
  ...featuresApi,
  ...keysApi,
  ...credentialsApi,
  ...modelsApi,
  ...myModelsApi,
  ...routesApi,
  ...budgetsApi,
  ...logsApi,
  ...alertsApi,
  ...entitlementsApi,
  ...pricingApi,
} as const
