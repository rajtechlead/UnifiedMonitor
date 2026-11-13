import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Shield } from 'lucide-react'
import { api } from '../hooks/useApi'
import { useAuthStore } from '../store/authStore'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const form = new FormData()
      form.append('username', email)
      form.append('password', password)
      const res = await api.post('/auth/login', form, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      setAuth(res.data.access_token, res.data.user)
      navigate('/')
    } catch (err: unknown) {
      setError('Invalid credentials. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleEntraLogin = () => {
    window.location.href = '/api/v1/auth/entra/login'
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--color-bg)',
      padding: 24,
    }}>
      <div style={{
        width: '100%',
        maxWidth: 420,
        background: 'var(--color-surface)',
        borderRadius: 16,
        padding: 40,
        border: '1px solid var(--color-border)',
        boxShadow: 'var(--shadow-md)',
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 56, height: 56, borderRadius: 14,
            background: 'var(--color-brand)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 12px',
          }}>
            <Shield size={28} color="white" />
          </div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: 'var(--color-brand)' }}>UniMonitor</h1>
          <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginTop: 4 }}>
            Unified M365 GRC Platform
          </p>
        </div>

        {/* Microsoft SSO button */}
        <button
          onClick={handleEntraLogin}
          style={{
            width: '100%', padding: '11px 16px',
            background: '#0078D4', color: 'white',
            border: 'none', borderRadius: 8, cursor: 'pointer',
            fontSize: 14, fontWeight: 600,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            marginBottom: 20,
          }}
        >
          <svg width="18" height="18" viewBox="0 0 21 21" fill="none">
            <rect x="1" y="1" width="9" height="9" fill="#F25022"/>
            <rect x="11" y="1" width="9" height="9" fill="#7FBA00"/>
            <rect x="1" y="11" width="9" height="9" fill="#00A4EF"/>
            <rect x="11" y="11" width="9" height="9" fill="#FFB900"/>
          </svg>
          Sign in with Microsoft
        </button>

        <div style={{
          display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20,
        }}>
          <div style={{ flex: 1, height: 1, background: 'var(--color-border)' }} />
          <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>or</span>
          <div style={{ flex: 1, height: 1, background: 'var(--color-border)' }} />
        </div>

        {/* Local login form */}
        <form onSubmit={handleLogin}>
          <div style={{ marginBottom: 16 }}>
            <label htmlFor="email" style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="admin@contoso.com"
              style={{
                width: '100%', padding: '10px 12px',
                border: '1px solid var(--color-border)',
                borderRadius: 8, background: 'var(--color-surface-2)',
                color: 'var(--color-text)', fontSize: 14, outline: 'none',
              }}
            />
          </div>
          <div style={{ marginBottom: 24 }}>
            <label htmlFor="password" style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="••••••••"
              style={{
                width: '100%', padding: '10px 12px',
                border: '1px solid var(--color-border)',
                borderRadius: 8, background: 'var(--color-surface-2)',
                color: 'var(--color-text)', fontSize: 14, outline: 'none',
              }}
            />
          </div>

          {error && (
            <div style={{
              padding: '10px 12px', marginBottom: 16,
              background: 'var(--color-critical-bg)', color: 'var(--color-critical)',
              borderRadius: 8, fontSize: 13,
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%', padding: '11px 16px',
              background: 'var(--color-brand)', color: 'white',
              border: 'none', borderRadius: 8, cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: 14, fontWeight: 600, opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  )
}
