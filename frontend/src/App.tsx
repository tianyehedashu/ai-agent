import { Routes, Route } from 'react-router-dom'

import { AuthProvider } from '@/components/auth-provider'
import Layout from '@/components/layout'
import { ThemeProvider } from '@/components/theme-provider'
import { Toaster } from '@/components/ui/toaster'
import AgentsPage from '@/pages/agents'
import LoginPage from '@/pages/auth/login'
import RegisterPage from '@/pages/auth/register'
import ChatPage from '@/pages/chat'
import GatewayLayout from '@/pages/gateway/_layout'
import GatewayAlertsPage from '@/pages/gateway/alerts'
import GatewayBudgetsPage from '@/pages/gateway/budgets'
import GatewayCredentialsPage from '@/pages/gateway/credentials'
import GatewayKeysPage from '@/pages/gateway/keys'
import GatewayLogsPage from '@/pages/gateway/logs'
import GatewayModelsPage from '@/pages/gateway/models'
import GatewayOverviewPage from '@/pages/gateway/overview'
import GatewayTeamsPage from '@/pages/gateway/teams'
import MCPPage from '@/pages/mcp'
import SystemMCPPage from '@/pages/mcp/system'
import NotFoundPage from '@/pages/not-found'
import ProductInfoPage from '@/pages/product-info'
import ProductInfoHistoryPage from '@/pages/product-info/history'
import ProductInfoHistoryDetailPage from '@/pages/product-info/history-detail'
import SettingsPage from '@/pages/settings'
import VideoTasksPage from '@/pages/video-tasks'
import VideoTasksHistoryPage from '@/pages/video-tasks/history'

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
                  <Route path="/agents" element={<AgentsPage />} />
                  <Route path="/mcp" element={<MCPPage />} />
                  <Route path="/mcp/system" element={<SystemMCPPage />} />
                  <Route path="/video-tasks" element={<VideoTasksPage />} />
                  <Route path="/video-tasks/history" element={<VideoTasksHistoryPage />} />
                  <Route path="/video-tasks/:sessionId" element={<VideoTasksPage />} />
                  <Route path="/product-info/:jobId?" element={<ProductInfoPage />} />
                  <Route path="/product-info/history" element={<ProductInfoHistoryPage />} />
                  <Route
                    path="/product-info/history/:id"
                    element={<ProductInfoHistoryDetailPage />}
                  />
                  <Route path="/settings" element={<SettingsPage />} />
                  <Route path="/gateway/*" element={<GatewayLayout />}>
                    <Route index element={<GatewayOverviewPage />} />
                    <Route path="overview" element={<GatewayOverviewPage />} />
                    <Route path="keys" element={<GatewayKeysPage />} />
                    <Route path="credentials" element={<GatewayCredentialsPage />} />
                    <Route path="models" element={<GatewayModelsPage />} />
                    <Route path="budgets" element={<GatewayBudgetsPage />} />
                    <Route path="logs" element={<GatewayLogsPage />} />
                    <Route path="alerts" element={<GatewayAlertsPage />} />
                    <Route path="teams" element={<GatewayTeamsPage />} />
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
