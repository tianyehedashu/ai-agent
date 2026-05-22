import { Suspense } from 'react'

import { Route, Routes } from 'react-router-dom'

import { AuthProvider } from '@/components/auth-provider'
import Layout from '@/components/layout'
import { RouteSuspenseFallback } from '@/components/route-suspense-fallback'
import { ThemeProvider } from '@/components/theme-provider'
import { Toaster } from '@/components/ui/toaster'
import { AppLayoutRoutes } from '@/routes/app-layout-routes'
import { LoginPage, RegisterPage } from '@/routes/lazy-pages'

function App(): React.JSX.Element {
  return (
    <ThemeProvider defaultTheme="dark" storageKey="ai-agent-theme">
      <AuthProvider>
        <Suspense fallback={<RouteSuspenseFallback />}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
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
      </AuthProvider>
    </ThemeProvider>
  )
}

export default App
