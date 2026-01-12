import { Routes, Route } from 'react-router-dom'

import Layout from '@/components/layout'
import { ThemeProvider } from '@/components/theme-provider'
import { Toaster } from '@/components/ui/toaster'
import AgentsPage from '@/pages/agents'
import ChatPage from '@/pages/chat'
import NotFoundPage from '@/pages/not-found'
import SettingsPage from '@/pages/settings'
import StudioPage from '@/pages/studio'

function App(): React.JSX.Element {
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
