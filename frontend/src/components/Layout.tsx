import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import {
  LayoutDashboard, Shield, CheckCircle, AlertTriangle,
  ClipboardList, FileText, Settings, LogOut, Moon, Sun, Menu, X,
} from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'

const NAV_ITEMS = [
  { to: '/executive', icon: LayoutDashboard, label: 'Executive' },
  { to: '/security', icon: Shield, label: 'Security' },
  { to: '/compliance', icon: CheckCircle, label: 'Compliance' },
  { to: '/findings', icon: AlertTriangle, label: 'Findings' },
  { to: '/assessments', icon: ClipboardList, label: 'Assessments' },
  { to: '/reports', icon: FileText, label: 'Reports' },
]

export default function Layout() {
  const { user, logout } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Sidebar */}
      <aside style={{
        width: sidebarOpen ? '240px' : '64px',
        background: 'var(--color-surface)',
        borderRight: '1px solid var(--color-border)',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 0.2s ease',
        flexShrink: 0,
        zIndex: 10,
      }}>
        {/* Logo */}
        <div style={{
          padding: '16px',
          borderBottom: '1px solid var(--color-border)',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          height: '56px',
        }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8, flexShrink: 0,
            background: 'var(--color-brand)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Shield size={18} color="white" />
          </div>
          {sidebarOpen && (
            <span style={{ fontWeight: 700, fontSize: 16, color: 'var(--color-brand)' }}>
              UniMonitor
            </span>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            style={{
              marginLeft: 'auto', background: 'none', border: 'none',
              color: 'var(--color-text-muted)', cursor: 'pointer', padding: 4,
            }}
          >
            {sidebarOpen ? <X size={16} /> : <Menu size={16} />}
          </button>
        </div>

        {/* Navigation */}
        <nav style={{ flex: 1, padding: '8px 0', overflowY: 'auto' }}>
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '10px 16px',
                color: isActive ? 'var(--color-brand)' : 'var(--color-text-secondary)',
                background: isActive ? 'rgba(23, 118, 210, 0.08)' : 'none',
                borderLeft: isActive ? '3px solid var(--color-brand)' : '3px solid transparent',
                textDecoration: 'none',
                fontSize: 14,
                fontWeight: isActive ? 600 : 400,
                transition: 'all 0.15s',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
              })}
            >
              <Icon size={18} style={{ flexShrink: 0 }} />
              {sidebarOpen && label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div style={{
          padding: '8px 0',
          borderTop: '1px solid var(--color-border)',
        }}>
          <NavLink
            to="/settings"
            style={({ isActive }) => ({
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '10px 16px',
              color: isActive ? 'var(--color-brand)' : 'var(--color-text-secondary)',
              textDecoration: 'none', fontSize: 14,
              borderLeft: isActive ? '3px solid var(--color-brand)' : '3px solid transparent',
            })}
          >
            <Settings size={18} style={{ flexShrink: 0 }} />
            {sidebarOpen && 'Settings'}
          </NavLink>
          <button
            onClick={toggleTheme}
            style={{
              display: 'flex', alignItems: 'center', gap: 10,
              width: '100%', padding: '10px 16px', background: 'none',
              border: 'none', color: 'var(--color-text-secondary)',
              cursor: 'pointer', fontSize: 14,
            }}
          >
            {theme === 'dark'
              ? <Sun size={18} style={{ flexShrink: 0 }} />
              : <Moon size={18} style={{ flexShrink: 0 }} />}
            {sidebarOpen && (theme === 'dark' ? 'Light Mode' : 'Dark Mode')}
          </button>
          <button
            onClick={handleLogout}
            style={{
              display: 'flex', alignItems: 'center', gap: 10,
              width: '100%', padding: '10px 16px', background: 'none',
              border: 'none', color: 'var(--color-text-secondary)',
              cursor: 'pointer', fontSize: 14,
            }}
          >
            <LogOut size={18} style={{ flexShrink: 0 }} />
            {sidebarOpen && 'Sign Out'}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
        {/* Top bar */}
        <header style={{
          height: 56,
          borderBottom: '1px solid var(--color-border)',
          background: 'var(--color-surface)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 24px',
          gap: 12,
          flexShrink: 0,
        }}>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 16,
              background: 'var(--color-brand)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'white', fontSize: 12, fontWeight: 700,
            }}>
              {user?.fullName?.[0] || user?.email?.[0] || 'U'}
            </div>
            {user && (
              <div style={{ lineHeight: 1.3 }}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{user.fullName || user.email}</div>
                <div style={{ fontSize: 11, color: 'var(--color-text-muted)', textTransform: 'capitalize' }}>
                  {user.role}
                </div>
              </div>
            )}
          </div>
        </header>

        {/* Page content */}
        <div style={{ flex: 1, padding: '24px', overflow: 'auto' }}>
          <Outlet />
        </div>
      </main>
    </div>
  )
}
