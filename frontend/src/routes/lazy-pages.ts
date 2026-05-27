import { lazyWithReload } from '@/lib/lazy-with-reload'

/** 路由级 code splitting：按页 lazy import，避免打进主 chunk */
export const LoginPage = lazyWithReload(() => import('@/pages/auth/login'))
export const RegisterPage = lazyWithReload(() => import('@/pages/auth/register'))

export const ChatPage = lazyWithReload(() => import('@/pages/chat'))
export const AgentsPage = lazyWithReload(() => import('@/pages/agents'))
export const MCPPage = lazyWithReload(() => import('@/pages/mcp'))
export const SystemMCPPage = lazyWithReload(() => import('@/pages/mcp/system'))
export const AdminStoragePage = lazyWithReload(() => import('@/pages/admin/storage'))
export const AdminUsersPage = lazyWithReload(() => import('@/pages/admin/users'))

export const VideoTasksPage = lazyWithReload(() => import('@/pages/video-tasks'))
export const VideoTasksHistoryPage = lazyWithReload(() => import('@/pages/video-tasks/history'))

export const ListingStudioPage = lazyWithReload(() => import('@/pages/listing-studio'))
export const ListingStudioHistoryPage = lazyWithReload(
  () => import('@/pages/listing-studio/history')
)
export const ListingStudioHistoryDetailPage = lazyWithReload(
  () => import('@/pages/listing-studio/history-detail')
)

export const SettingsPage = lazyWithReload(() => import('@/pages/settings'))
export const NotFoundPage = lazyWithReload(() => import('@/pages/not-found'))

export const GatewayLayout = lazyWithReload(() => import('@/pages/gateway/_layout'))
export const GatewayTeamRedirect = lazyWithReload(
  () => import('@/pages/gateway/gateway-team-redirect')
)
export const GatewayGuidePage = lazyWithReload(() => import('@/pages/gateway/guide'))
export const GatewayPlatformStatsPage = lazyWithReload(
  () => import('@/pages/gateway/platform-stats')
)
export const GatewayOverviewPage = lazyWithReload(() => import('@/pages/gateway/overview'))
export const GatewayStatsPage = lazyWithReload(() => import('@/pages/gateway/stats'))
export const GatewayKeysPage = lazyWithReload(() => import('@/pages/gateway/keys'))
export const GatewayCredentialsPage = lazyWithReload(() => import('@/pages/gateway/credentials'))
export const GatewayCredentialDetailPage = lazyWithReload(
  () => import('@/pages/gateway/credential-detail')
)
export const GatewayModelsPage = lazyWithReload(() => import('@/pages/gateway/models'))
export const GatewayModelDetailPage = lazyWithReload(() => import('@/pages/gateway/model-detail'))
export const GatewayRoutesPage = lazyWithReload(() => import('@/pages/gateway/routes'))
export const GatewayPricingLayout = lazyWithReload(() => import('@/pages/gateway/pricing/_layout'))
export const GatewayPricingMyPricesPage = lazyWithReload(
  () => import('@/pages/gateway/pricing/my-prices')
)
export const GatewayPricingDownstreamPage = lazyWithReload(
  () => import('@/pages/gateway/pricing/downstream')
)
export const GatewayPricingUpstreamPage = lazyWithReload(
  () => import('@/pages/gateway/pricing/upstream')
)
export const GatewayBudgetsPage = lazyWithReload(() => import('@/pages/gateway/budgets'))
export const GatewayLogsPage = lazyWithReload(() => import('@/pages/gateway/logs'))
export const GatewayTeamsPage = lazyWithReload(() => import('@/pages/gateway/teams'))
