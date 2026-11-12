import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import Layout from './components/Layout'
import { ErrorBoundary } from './components/ErrorBoundary'
import ExecutiveDashboard from './pages/ExecutiveDashboard'
import SecurityDashboard from './pages/SecurityDashboard'
import ComplianceDashboard from './pages/ComplianceDashboard'
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
        <Routes>
          <Route path="/login" element={<LoginPage />} />
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
            <Route path="security" element={<RouteErrorBoundary><SecurityDashboard /></RouteErrorBoundary>} />
            <Route path="compliance" element={<RouteErrorBoundary><ComplianceDashboard /></RouteErrorBoundary>} />
            <Route path="findings" element={<RouteErrorBoundary><FindingsPage /></RouteErrorBoundary>} />
            <Route path="assessments" element={<RouteErrorBoundary><AssessmentsPage /></RouteErrorBoundary>} />
            <Route path="reports" element={<RouteErrorBoundary><ReportsPage /></RouteErrorBoundary>} />
            <Route path="settings" element={<RouteErrorBoundary><SettingsPage /></RouteErrorBoundary>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
