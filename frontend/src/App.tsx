import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { api } from './hooks/useApi'
import SetupPage from './pages/SetupPage'
import Layout from './components/Layout'
import { ErrorBoundary } from './components/ErrorBoundary'
import ExecutiveDashboard from './pages/ExecutiveDashboard'
import SecurityDashboard from './pages/SecurityDashboard'
import ComplianceDashboard from './pages/ComplianceDashboard'
import RiskDashboard from './pages/RiskDashboard'
import SocDashboard from './pages/SocDashboard'
import CloudDashboard from './pages/CloudDashboard'
import CisoDashboard from './pages/CisoDashboard'
import CloudProviderPage from './pages/CloudProviderPage'
import ZeroTrustPage from './pages/ZeroTrustPage'
import AlertsPage from './pages/AlertsPage'
import LicensesPage from './pages/LicensesPage'
import ServiceHealthPage from './pages/ServiceHealthPage'
import CollectionPage from './pages/CollectionPage'
import AuditPage from './pages/AuditPage'
import FindingsPage from './pages/FindingsPage'
import AssessmentsPage from './pages/AssessmentsPage'
import ReportsPage from './pages/ReportsPage'
import SettingsPage from './pages/SettingsPage'
import LoginPage from './pages/LoginPage'
import { useAuthStore } from './store/authStore'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

/**
 * Sends a fresh install to /setup: with no administrator and no platform connected
 * the dashboard has nothing to show. Once setup is complete the check stops running.
 */
function SetupGate({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null)

  useEffect(() => {
    if (needsSetup === false) return
    let cancelled = false
    api.get('/onboarding/status')
      .then((res) => { if (!cancelled) setNeedsSetup(Boolean(res.data.needs_admin)) })
      .catch(() => { if (!cancelled) setNeedsSetup(false) })
    return () => { cancelled = true }
  }, [location.pathname, needsSetup])

  if (needsSetup && location.pathname !== '/setup') return <Navigate to="/setup" replace />
  return <>{children}</>
}

/**
 * RouteErrorBoundary resets the error boundary on every navigation.
 * Wrap each page-level route so a crash in one page doesn't lock the whole app.
 */
function RouteErrorBoundary({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  return (
    <ErrorBoundary resetKey={location.pathname}>
      {children}
    </ErrorBoundary>
  )
}

export default function App() {
  return (
    // Top-level boundary catches errors in Layout, auth checks, etc.
    <ErrorBoundary>
      <BrowserRouter>
        <SetupGate>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/setup" element={<SetupPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/executive" replace />} />
            <Route path="executive" element={<RouteErrorBoundary><ExecutiveDashboard /></RouteErrorBoundary>} />
            <Route path="ciso" element={<RouteErrorBoundary><CisoDashboard /></RouteErrorBoundary>} />
            <Route path="clouds" element={<RouteErrorBoundary><CloudDashboard /></RouteErrorBoundary>} />
            <Route path="zero-trust" element={<RouteErrorBoundary><ZeroTrustPage /></RouteErrorBoundary>} />
            <Route path="clouds/:providerId" element={<RouteErrorBoundary><CloudProviderPage /></RouteErrorBoundary>} />
            <Route path="security" element={<RouteErrorBoundary><SecurityDashboard /></RouteErrorBoundary>} />
            <Route path="compliance" element={<RouteErrorBoundary><ComplianceDashboard /></RouteErrorBoundary>} />
            <Route path="risk" element={<RouteErrorBoundary><RiskDashboard /></RouteErrorBoundary>} />
            <Route path="soc" element={<RouteErrorBoundary><SocDashboard /></RouteErrorBoundary>} />
            <Route path="audit" element={<RouteErrorBoundary><AuditPage /></RouteErrorBoundary>} />
            <Route path="findings" element={<RouteErrorBoundary><FindingsPage /></RouteErrorBoundary>} />
            <Route path="alerts" element={<RouteErrorBoundary><AlertsPage /></RouteErrorBoundary>} />
            <Route path="licenses" element={<RouteErrorBoundary><LicensesPage /></RouteErrorBoundary>} />
            <Route path="service-health" element={<RouteErrorBoundary><ServiceHealthPage /></RouteErrorBoundary>} />
            <Route path="collection" element={<RouteErrorBoundary><CollectionPage /></RouteErrorBoundary>} />
            <Route path="assessments" element={<RouteErrorBoundary><AssessmentsPage /></RouteErrorBoundary>} />
            <Route path="reports" element={<RouteErrorBoundary><ReportsPage /></RouteErrorBoundary>} />
            <Route path="settings" element={<RouteErrorBoundary><SettingsPage /></RouteErrorBoundary>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </SetupGate>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
