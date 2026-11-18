import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle, ChevronRight, Database, Plug, ShieldCheck, UserPlus } from 'lucide-react'
import { api } from '../hooks/useApi'
import { useAuthStore } from '../store/authStore'
import PlatformConnector, { GoogleSharedConnector, type Connection, type Platform } from '../components/PlatformConnector'

type SetupStatus = {
  needs_admin: boolean
  configured: boolean
  connections: Connection[]
  platforms: Platform[]
  manual_follow_up: string
}

const card: React.CSSProperties = {
  background: 'var(--color-surface)', border: '1px solid var(--color-border)',
  borderRadius: 14, padding: 28, width: '100%', maxWidth: 720,
}
const label: React.CSSProperties = { display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }
const input: React.CSSProperties = {
  width: '100%', padding: '9px 12px', fontSize: 13, borderRadius: 7,
  border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
  color: 'var(--color-text)', outline: 'none',
}

function AlreadyConfigured({ status, onGo }: Readonly<{ status: SetupStatus; onGo: () => void }>) {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--color-bg)' }}>
      <div style={card}>
        <ShieldCheck size={28} color="var(--color-brand)" />
        <h2 style={{ margin: '12px 0 6px', fontSize: 18 }}>UniMonitor is already set up</h2>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          {status.connections.map((c) => c.display_name).join(', ')} connected. Add more platforms from
          Settings → Platform connections.
        </p>
        <button onClick={onGo} style={primaryBtn}>Go to the dashboard</button>
      </div>
    </div>
  )
}

function StepHeader({ n, title, active, done }: Readonly<{ n: number; title: string; active: boolean; done: boolean }>) {
  const badgeBackground = done ? '#22c55e' : active ? 'var(--color-brand)' : 'var(--color-surface-2)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
      <div style={{
        width: 26, height: 26, borderRadius: 13, display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 12, fontWeight: 700,
        background: badgeBackground,
        color: done || active ? '#fff' : 'var(--color-text-muted)',
      }}>
        {done ? <CheckCircle size={15} /> : n}
      </div>
      <span style={{ fontSize: 15, fontWeight: 600 }}>{title}</span>
    </div>
  )
}

/**
 * First-run setup: create the administrator, choose at least one platform, connect it.
 * The platform list is what makes a fresh install useful — a dashboard with no
 * connected cloud shows nothing, so the selection is required, not optional.
 */
export default function SetupPage() {
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)

  const [status, setStatus] = useState<SetupStatus | null>(null)
  const [step, setStep] = useState(1)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [organisation, setOrganisation] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [sharedGoogle, setSharedGoogle] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = async () => {
    const res = await api.get('/onboarding/status')
    setStatus(res.data)
    if (!res.data.needs_admin) setStep(2)
  }

  useEffect(() => { load().catch(() => setError('Could not reach the UniMonitor API.')) }, [])

  const connections = useMemo(() => {
    const map: Record<string, Connection> = {}
    for (const c of status?.connections || []) map[c.provider] = c
    return map
  }, [status])

  const selectedPlatforms = (status?.platforms || []).filter((p) => selected.includes(p.id))
  const allSelectedConnected = selectedPlatforms.length > 0
    && selectedPlatforms.every((p) => connections[p.id]?.status === 'connected')
  const googleBothSelected = selected.includes('gcp') && selected.includes('google_workspace')
  const useSharedGoogle = sharedGoogle && googleBothSelected
    && !(connections.gcp?.status === 'connected' && connections.google_workspace?.status === 'connected')

  const createAdmin = async () => {
    setError(''); setBusy(true)
    try {
      const res = await api.post('/onboarding/admin', { email, password, organisation })
      setAuth(res.data.access_token, {
        id: '', email: res.data.user.email, fullName: 'Administrator',
        role: res.data.user.role, tenantId: '',
      })
      await load()
      setStep(2)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Could not create the administrator account.')
    } finally {
      setBusy(false)
    }
  }

  const toggle = (id: string) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]))

  const onConnected = async () => { await load() }

  if (!status) {
    return <div style={{ padding: 40, color: 'var(--color-text-muted)' }}>Loading setup…</div>
  }

  // Setup finished earlier: no reason to show the wizard again.
  if (status.configured && step !== 4) {
    return <AlreadyConfigured status={status} onGo={() => navigate('/')} />
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--color-bg)', display: 'flex', justifyContent: 'center', padding: '40px 20px' }}>
      <div style={{ width: '100%', maxWidth: 720, display: 'flex', flexDirection: 'column', gap: 18 }}>
        <div>
          <h1 style={{ fontSize: 22, margin: 0 }}>Set up UniMonitor</h1>
          <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginTop: 6 }}>
            Choose the platforms to monitor. You can add more later — at least one is required now.
          </p>
        </div>

        {/* ── Step 1 — administrator ─────────────────────────────────────── */}
        <div style={card}>
          <StepHeader n={1} title="Administrator account" active={step === 1} done={step > 1} />
          {step === 1 ? (
            <div>
              <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 14 }}>
                <Database size={13} /> The database is created automatically. This account signs in to this install.
              </p>
              <label htmlFor="admin-email" style={label}>Email</label>
              <input id="admin-email" style={input} value={email} onChange={(e) => setEmail(e.target.value)} placeholder="admin@example.com" />
              <div style={{ height: 10 }} />
              <label htmlFor="admin-password" style={label}>Password (at least 12 characters)</label>
              <input id="admin-password" style={input} type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
              <div style={{ height: 10 }} />
              <label htmlFor="admin-organisation" style={label}>Organisation (optional)</label>
              <input id="admin-organisation" style={input} value={organisation} onChange={(e) => setOrganisation(e.target.value)} placeholder="Contoso Ltd" />
              {error && <p style={{ color: 'var(--color-high)', fontSize: 13, marginTop: 12 }}>{error}</p>}
              <button onClick={createAdmin} disabled={busy || !email || password.length < 12} style={primaryBtn}>
                <UserPlus size={15} /> {busy ? 'Creating…' : 'Create administrator'}
              </button>
            </div>
          ) : (
            <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
              {isAuthenticated ? 'Administrator created.' : 'Administrator already exists.'}
            </p>
          )}
        </div>

        {/* ── Step 2 — platform selection ────────────────────────────────── */}
        <div style={card}>
          <StepHeader n={2} title="Platforms to monitor" active={step === 2} done={step > 2} />
          {step === 2 ? (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 10 }}>
                {status.platforms.map((p) => {
                  const checked = selected.includes(p.id) || Boolean(connections[p.id])
                  return (
                    <button
                      key={p.id}
                      onClick={() => toggle(p.id)}
                      style={{
                        textAlign: 'left', padding: 14, borderRadius: 10, cursor: 'pointer',
                        border: `1px solid ${checked ? p.colour : 'var(--color-border)'}`,
                        background: checked ? `${p.colour}14` : 'var(--color-surface-2)',
                        color: 'var(--color-text)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ fontSize: 13, fontWeight: 600 }}>{p.name}</span>
                        <input type="checkbox" checked={checked} readOnly tabIndex={-1} />
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 4 }}>{p.description}</div>
                    </button>
                  )
                })}
              </div>
              {error && <p style={{ color: 'var(--color-high)', fontSize: 13, marginTop: 12 }}>{error}</p>}
              <button
                onClick={() => setStep(3)}
                disabled={selected.length === 0}
                style={{ ...primaryBtn, opacity: selected.length === 0 ? 0.5 : 1 }}
              >
                Continue <ChevronRight size={15} />
              </button>
              {selected.length === 0 && (
                <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 8 }}>
                  Select at least one platform.
                </p>
              )}
            </div>
          ) : (
            <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
              {selectedPlatforms.map((p) => p.name).join(', ') || 'None selected'}
            </p>
          )}
        </div>

        {/* ── Step 3 — connection ────────────────────────────────────────── */}
        <div style={{ ...card, opacity: step < 3 ? 0.6 : 1 }}>
          <StepHeader n={3} title="Connect" active={step === 3} done={step > 3} />
          {step === 3 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              {useSharedGoogle && (
                <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                    <Plug size={15} color="#4285F4" />
                    <span style={{ fontSize: 14, fontWeight: 600 }}>Google Cloud + Google Workspace</span>
                  </div>
                  <GoogleSharedConnector onConnected={() => { void onConnected() }} />
                  <button
                    onClick={() => setSharedGoogle(false)}
                    style={{ marginTop: 10, background: 'none', border: 'none', color: 'var(--color-text-muted)', fontSize: 12, cursor: 'pointer', padding: 0 }}
                  >
                    Use separate service accounts instead
                  </button>
                </div>
              )}
              {selectedPlatforms.filter((p) => !(useSharedGoogle && (p.id === 'gcp' || p.id === 'google_workspace'))).map((p) => (
                <div key={p.id} style={{ borderTop: '1px solid var(--color-border)', paddingTop: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                    <Plug size={15} color={p.colour} />
                    <span style={{ fontSize: 14, fontWeight: 600 }}>{p.name}</span>
                  </div>
                  <PlatformConnector platform={p} connected={connections[p.id]} onConnected={onConnected} />
                </div>
              ))}
              {status.manual_follow_up && (
                <p style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{status.manual_follow_up}</p>
              )}
              <button
                onClick={() => { setStep(4); navigate('/') }}
                disabled={!allSelectedConnected}
                style={{ ...primaryBtn, opacity: allSelectedConnected ? 1 : 0.5 }}
              >
                Finish setup <ChevronRight size={15} />
              </button>
              {!allSelectedConnected && (
                <p style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                  Connect every selected platform to finish — or remove one from step 2.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

const primaryBtn: React.CSSProperties = {
  marginTop: 18, display: 'inline-flex', alignItems: 'center', gap: 8,
  padding: '10px 16px', borderRadius: 8, border: 'none', cursor: 'pointer',
  background: 'var(--color-brand)', color: '#fff', fontSize: 13, fontWeight: 600,
}
