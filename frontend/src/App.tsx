import { Suspense } from 'react'

import { Route, Routes } from 'react-router-dom'

import { AuthProvider } from '@/components/auth-provider'
import Layout from '@/components/layout'
import { RouteSuspenseFallback } from '@/components/route-suspense-fallback'
import { ThemeProvider } from '@/components/theme-provider'
import { Toaster } from '@/components/ui/toaster'
import { TooltipProvider } from '@/components/ui/tooltip'
import { AppLayoutRoutes } from '@/routes/app-layout-routes'
import { LoginPage, RegisterPage, SsoCallbackPage } from '@/routes/lazy-pages'

function App(): React.JSX.Element {
  return (
    <ThemeProvider defaultTheme="dark" storageKey="ai-agent-theme">
      <AuthProvider>
        <TooltipProvider delayDuration={200}>
          <Suspense fallback={<RouteSuspenseFallback />}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/sso-callback" element={<SsoCallbackPage />} />
              <Route
                path="/*"
                element={
                  <Layout>
                    <AppLayoutRoutes />
                  </Layout>
                }
              />
            </Routes>
          </Suspense>
          <Toaster />
        </TooltipProvider>
      </AuthProvider>
    </ThemeProvider>
  )
}

export default App
