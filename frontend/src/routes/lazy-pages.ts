import { lazy } from 'react'

/** 路由级 code splitting：按页 lazy import，避免打进主 chunk */
export const LoginPage = lazy(() => import('@/pages/auth/login'))
export const RegisterPage = lazy(() => import('@/pages/auth/register'))

export const ChatPage = lazy(() => import('@/pages/chat'))
export const AgentsPage = lazy(() => import('@/pages/agents'))
export const MCPPage = lazy(() => import('@/pages/mcp'))
export const SystemMCPPage = lazy(() => import('@/pages/mcp/system'))
export const AdminStoragePage = lazy(() => import('@/pages/admin/storage'))

export const VideoTasksPage = lazy(() => import('@/pages/video-tasks'))
export const VideoTasksHistoryPage = lazy(() => import('@/pages/video-tasks/history'))

export const ListingStudioPage = lazy(() => import('@/pages/listing-studio'))
export const ListingStudioHistoryPage = lazy(() => import('@/pages/listing-studio/history'))
export const ListingStudioHistoryDetailPage = lazy(
  () => import('@/pages/listing-studio/history-detail')
)

export const SettingsPage = lazy(() => import('@/pages/settings'))
export const NotFoundPage = lazy(() => import('@/pages/not-found'))

export const GatewayLayout = lazy(() => import('@/pages/gateway/_layout'))
export const GatewayTeamRedirect = lazy(() => import('@/pages/gateway/gateway-team-redirect'))
export const GatewayGuidePage = lazy(() => import('@/pages/gateway/guide'))
export const GatewayPlatformStatsPage = lazy(() => import('@/pages/gateway/platform-stats'))
export const GatewayOverviewPage = lazy(() => import('@/pages/gateway/overview'))
export const GatewayStatsPage = lazy(() => import('@/pages/gateway/stats'))
export const GatewayKeysPage = lazy(() => import('@/pages/gateway/keys'))
export const GatewayCredentialsPage = lazy(() => import('@/pages/gateway/credentials'))
export const GatewayCredentialDetailPage = lazy(() => import('@/pages/gateway/credential-detail'))
export const GatewayModelsPage = lazy(() => import('@/pages/gateway/models'))
export const GatewayModelDetailPage = lazy(() => import('@/pages/gateway/model-detail'))
export const GatewayRoutesPage = lazy(() => import('@/pages/gateway/routes'))
export const GatewayPricingLayout = lazy(() => import('@/pages/gateway/pricing/_layout'))
export const GatewayPricingMyPricesPage = lazy(() => import('@/pages/gateway/pricing/my-prices'))
export const GatewayPricingDownstreamPage = lazy(() => import('@/pages/gateway/pricing/downstream'))
export const GatewayPricingUpstreamPage = lazy(() => import('@/pages/gateway/pricing/upstream'))
export const GatewayBudgetsPage = lazy(() => import('@/pages/gateway/budgets'))
export const GatewayLogsPage = lazy(() => import('@/pages/gateway/logs'))
export const GatewayTeamsPage = lazy(() => import('@/pages/gateway/teams'))
