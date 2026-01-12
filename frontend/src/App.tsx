import { Routes, Route } from 'react-router-dom'
import { Toaster } from '@/components/ui/toaster'
import { ThemeProvider } from '@/components/theme-provider'
import Layout from '@/components/layout'
import ChatPage from '@/pages/chat'
import AgentsPage from '@/pages/agents'
import StudioPage from '@/pages/studio'
import SettingsPage from '@/pages/settings'
import NotFoundPage from '@/pages/not-found'

function App() {
  return (
    <ThemeProvider defaultTheme="dark" storageKey="ai-agent-theme">
      <Layout>
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/chat/:sessionId?" element={<ChatPage />} />
          <Route path="/agents" element={<AgentsPage />} />
          <Route path="/studio" element={<StudioPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Layout>
      <Toaster />
    </ThemeProvider>
  )
}

export default App
