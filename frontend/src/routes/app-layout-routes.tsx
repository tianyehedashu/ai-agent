import { Navigate, useLocation, useRoutes, type RouteObject } from 'react-router-dom'

import { RequirePlatformAdmin } from '@/components/require-platform-admin'
import {
  AdminStoragePage,
  AdminUsersPage,
  AgentsPage,
  ChatPage,
  GatewayBudgetsPage,
  GatewayCredentialDetailPage,
  GatewayCredentialsPage,
  GatewayGuidePage,
  GatewayKeysPage,
  GatewayLayout,
  GatewayLogsPage,
  GatewayModelDetailPage,
  GatewayModelsPage,
  GatewayOverviewPage,
  GatewayPlatformStatsPage,
  GatewayPricingDownstreamPage,
  GatewayPricingLayout,
  GatewayPricingMyPricesPage,
  GatewayPricingUpstreamPage,
  GatewayRoutesPage,
  GatewayStatsPage,
  GatewayTeamRedirect,
  GatewayTeamsPage,
  ListingStudioHistoryDetailPage,
  ListingStudioHistoryPage,
  ListingStudioPage,
  MCPPage,
  NotFoundPage,
  SettingsPage,
  SystemMCPPage,
  VideoTasksHistoryPage,
  VideoTasksPage,
} from '@/routes/lazy-pages'
import { RoutePageOutlet } from '@/routes/route-page-outlet'

function LegacyProductInfoRedirect(): React.JSX.Element {
  const { pathname } = useLocation()
  const target = pathname.replace(/^\/product-info/, '/listing-studio') || '/listing-studio'
  return <Navigate to={target} replace />
}

const appLayoutRouteConfig: RouteObject[] = [
  { path: '/', element: <Navigate to="/chat" replace /> },
  { path: '/chat/:sessionId?', element: <ChatPage /> },
  {
    path: '/agents',
    element: (
      <RequirePlatformAdmin>
        <AgentsPage />
      </RequirePlatformAdmin>
    ),
  },
  {
    path: '/mcp',
    element: (
      <RequirePlatformAdmin>
        <MCPPage />
      </RequirePlatformAdmin>
    ),
  },
  { path: '/mcp/system', element: <SystemMCPPage /> },
  { path: '/admin/storage', element: <AdminStoragePage /> },
  {
    path: '/admin/users',
    element: (
      <RequirePlatformAdmin>
        <AdminUsersPage />
      </RequirePlatformAdmin>
    ),
  },
  { path: '/video-tasks', element: <VideoTasksPage /> },
  { path: '/video-tasks/history', element: <VideoTasksHistoryPage /> },
  { path: '/video-tasks/:sessionId', element: <VideoTasksPage /> },
  { path: '/listing-studio/history', element: <ListingStudioHistoryPage /> },
  { path: '/listing-studio/history/:id', element: <ListingStudioHistoryDetailPage /> },
  { path: '/listing-studio/:jobId?', element: <ListingStudioPage /> },
  { path: '/product-info/*', element: <LegacyProductInfoRedirect /> },
  { path: '/settings', element: <SettingsPage /> },
  {
    path: '/gateway/*',
    element: <GatewayLayout />,
    children: [
      { index: true, element: <GatewayTeamRedirect /> },
      { path: 'guide', element: <GatewayGuidePage /> },
      { path: 'platform-stats', element: <GatewayPlatformStatsPage /> },
      {
        path: 'teams/:teamId',
        children: [
          { index: true, element: <Navigate to="overview" replace /> },
          { path: 'overview', element: <GatewayOverviewPage /> },
          { path: 'stats', element: <GatewayStatsPage /> },
          { path: 'keys', element: <GatewayKeysPage /> },
          { path: 'credentials', element: <GatewayCredentialsPage /> },
          { path: 'credentials/:credentialId', element: <GatewayCredentialDetailPage /> },
          { path: 'models', element: <GatewayModelsPage /> },
          { path: 'models/:modelId', element: <GatewayModelDetailPage /> },
          { path: 'routes', element: <GatewayRoutesPage /> },
          {
            path: 'pricing',
            element: <GatewayPricingLayout />,
            children: [
              { index: true, element: <GatewayPricingMyPricesPage /> },
              { path: 'my-prices', element: <GatewayPricingMyPricesPage /> },
              { path: 'downstream', element: <GatewayPricingDownstreamPage /> },
              { path: 'upstream', element: <GatewayPricingUpstreamPage /> },
            ],
          },
          { path: 'budgets', element: <GatewayBudgetsPage /> },
          { path: 'logs', element: <GatewayLogsPage /> },
          { path: 'alerts', element: <Navigate to="overview" replace relative="path" /> },
          { path: 'members', element: <GatewayTeamsPage /> },
        ],
      },
      { path: 'overview', element: <GatewayTeamRedirect /> },
      { path: 'stats', element: <GatewayTeamRedirect /> },
      { path: 'keys', element: <GatewayTeamRedirect /> },
      { path: 'credentials', element: <GatewayTeamRedirect /> },
      { path: 'credentials/:credentialId', element: <GatewayTeamRedirect /> },
      { path: 'models', element: <GatewayTeamRedirect /> },
      { path: 'models/:modelId', element: <GatewayTeamRedirect /> },
      { path: 'routes', element: <GatewayTeamRedirect /> },
      { path: 'pricing/*', element: <GatewayTeamRedirect /> },
      { path: 'budgets', element: <GatewayTeamRedirect /> },
      { path: 'logs', element: <GatewayTeamRedirect /> },
      { path: 'alerts', element: <GatewayTeamRedirect /> },
      { path: 'teams', element: <GatewayTeamRedirect /> },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
]

export function AppLayoutRoutes(): React.JSX.Element | null {
  const location = useLocation()
  const element = useRoutes(appLayoutRouteConfig)
  return <RoutePageOutlet pathname={location.pathname}>{element}</RoutePageOutlet>
}
