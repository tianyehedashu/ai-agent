import { Routes, Route, Navigate, useLocation } from 'react-router-dom'

import { AuthProvider } from '@/components/auth-provider'
import Layout from '@/components/layout'
import { RequirePlatformAdmin } from '@/components/require-platform-admin'
import { ThemeProvider } from '@/components/theme-provider'
import { Toaster } from '@/components/ui/toaster'
import AdminStoragePage from '@/pages/admin/storage'
import AgentsPage from '@/pages/agents'
import LoginPage from '@/pages/auth/login'
import RegisterPage from '@/pages/auth/register'
import ChatPage from '@/pages/chat'
import GatewayLayout from '@/pages/gateway/_layout'
import GatewayBudgetsPage from '@/pages/gateway/budgets'
import GatewayCredentialDetailPage from '@/pages/gateway/credential-detail'
import GatewayCredentialsPage from '@/pages/gateway/credentials'
import GatewayTeamRedirect from '@/pages/gateway/gateway-team-redirect'
import GatewayGuidePage from '@/pages/gateway/guide'
import GatewayKeysPage from '@/pages/gateway/keys'
import GatewayLogsPage from '@/pages/gateway/logs'
import GatewayModelDetailPage from '@/pages/gateway/model-detail'
import GatewayModelsPage from '@/pages/gateway/models'
import GatewayOverviewPage from '@/pages/gateway/overview'
import GatewayPlatformStatsPage from '@/pages/gateway/platform-stats'
import GatewayPricingLayout from '@/pages/gateway/pricing/_layout'
import GatewayPricingDownstreamPage from '@/pages/gateway/pricing/downstream'
import GatewayPricingMyPricesPage from '@/pages/gateway/pricing/my-prices'
import GatewayPricingUpstreamPage from '@/pages/gateway/pricing/upstream'
import GatewayRoutesPage from '@/pages/gateway/routes'
import GatewayTeamsPage from '@/pages/gateway/teams'
import ListingStudioPage from '@/pages/listing-studio'
import ListingStudioHistoryPage from '@/pages/listing-studio/history'
import ListingStudioHistoryDetailPage from '@/pages/listing-studio/history-detail'
import MCPPage from '@/pages/mcp'
import SystemMCPPage from '@/pages/mcp/system'
import NotFoundPage from '@/pages/not-found'
import SettingsPage from '@/pages/settings'
import VideoTasksPage from '@/pages/video-tasks'
import VideoTasksHistoryPage from '@/pages/video-tasks/history'

function LegacyProductInfoRedirect(): React.JSX.Element {
  const { pathname } = useLocation()
  const target = pathname.replace(/^\/product-info/, '/listing-studio') || '/listing-studio'
  return <Navigate to={target} replace />
}

function App(): React.JSX.Element {
  return (
    <ThemeProvider defaultTheme="dark" storageKey="ai-agent-theme">
      <AuthProvider>
        <Routes>
          {/* Auth Routes - No Layout */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Protected Routes - With Layout */}
          <Route
            path="/*"
            element={
              <Layout>
                <Routes>
                  <Route path="/" element={<ChatPage />} />
                  <Route path="/chat/:sessionId?" element={<ChatPage />} />
                  <Route
                    path="/agents"
                    element={
                      <RequirePlatformAdmin>
                        <AgentsPage />
                      </RequirePlatformAdmin>
                    }
                  />
                  <Route path="/mcp" element={<MCPPage />} />
                  <Route
                    path="/mcp/system"
                    element={
                      <RequirePlatformAdmin>
                        <SystemMCPPage />
                      </RequirePlatformAdmin>
                    }
                  />
                  <Route path="/admin/storage" element={<AdminStoragePage />} />
                  <Route path="/video-tasks" element={<VideoTasksPage />} />
                  <Route path="/video-tasks/history" element={<VideoTasksHistoryPage />} />
                  <Route path="/video-tasks/:sessionId" element={<VideoTasksPage />} />
                  <Route path="/listing-studio/history" element={<ListingStudioHistoryPage />} />
                  <Route
                    path="/listing-studio/history/:id"
                    element={<ListingStudioHistoryDetailPage />}
                  />
                  {/* 静态段须在 :jobId? 之前，避免 history 被当作 jobId */}
                  <Route path="/listing-studio/:jobId?" element={<ListingStudioPage />} />
                  <Route path="/product-info/*" element={<LegacyProductInfoRedirect />} />
                  <Route path="/settings" element={<SettingsPage />} />
                  <Route path="/gateway/*" element={<GatewayLayout />}>
                    <Route index element={<GatewayTeamRedirect />} />
                    <Route path="guide" element={<GatewayGuidePage />} />
                    <Route path="platform-stats" element={<GatewayPlatformStatsPage />} />
                    <Route path="teams/:teamId">
                      <Route index element={<Navigate to="overview" replace />} />
                      <Route path="overview" element={<GatewayOverviewPage />} />
                      <Route path="keys" element={<GatewayKeysPage />} />
                      <Route path="credentials" element={<GatewayCredentialsPage />} />
                      <Route
                        path="credentials/:credentialId"
                        element={<GatewayCredentialDetailPage />}
                      />
                      <Route path="models" element={<GatewayModelsPage />} />
                      <Route path="models/:modelId" element={<GatewayModelDetailPage />} />
                      <Route path="routes" element={<GatewayRoutesPage />} />
                      <Route path="pricing" element={<GatewayPricingLayout />}>
                        <Route index element={<GatewayPricingMyPricesPage />} />
                        <Route path="my-prices" element={<GatewayPricingMyPricesPage />} />
                        <Route path="downstream" element={<GatewayPricingDownstreamPage />} />
                        <Route path="upstream" element={<GatewayPricingUpstreamPage />} />
                      </Route>
                      <Route path="budgets" element={<GatewayBudgetsPage />} />
                      <Route path="logs" element={<GatewayLogsPage />} />
                      <Route
                        path="alerts"
                        element={<Navigate to="overview" replace relative="path" />}
                      />
                      <Route path="members" element={<GatewayTeamsPage />} />
                    </Route>
                    {/* Legacy flat paths → GatewayTeamRedirect */}
                    <Route path="overview" element={<GatewayTeamRedirect />} />
                    <Route path="keys" element={<GatewayTeamRedirect />} />
                    <Route path="credentials" element={<GatewayTeamRedirect />} />
                    <Route path="credentials/:credentialId" element={<GatewayTeamRedirect />} />
                    <Route path="models" element={<GatewayTeamRedirect />} />
                    <Route path="models/:modelId" element={<GatewayTeamRedirect />} />
                    <Route path="routes" element={<GatewayTeamRedirect />} />
                    <Route path="pricing/*" element={<GatewayTeamRedirect />} />
                    <Route path="budgets" element={<GatewayTeamRedirect />} />
                    <Route path="logs" element={<GatewayTeamRedirect />} />
                    <Route path="alerts" element={<GatewayTeamRedirect />} />
                    <Route path="teams" element={<GatewayTeamRedirect />} />
                  </Route>
                  <Route path="*" element={<NotFoundPage />} />
                </Routes>
              </Layout>
            }
          />
        </Routes>
        <Toaster />
      </AuthProvider>
    </ThemeProvider>
  )
}

export default App
