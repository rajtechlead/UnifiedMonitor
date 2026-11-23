import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { aiApi, api } from '../hooks/useApi'
import { Save, Bell, Mail, MessageSquare, Shield, Plug, Trash2, AlertTriangle, KeyRound, FileJson, Send, Webhook, Sparkles } from 'lucide-react'
import PlatformConnector, { GoogleSharedConnector, type Connection, type Platform } from '../components/PlatformConnector'
import BrandingPanel from '../components/BrandingPanel'
import DelegatedAccessPanel from '../components/DelegatedAccessPanel'

const GOOGLE_SHARED = '__google_shared'

type NotificationSettings = {
  smtp_enabled: boolean
  smtp_host?: string
  smtp_port?: number
  smtp_username?: string
  smtp_password?: string
  smtp_to_emails?: string[]
  teams_webhook_url?: string
  slack_webhook_url?: string
  immediate_alerts: boolean
  daily_digest: boolean
  weekly_digest: boolean
  alert_severity_threshold: string
}

function Section({ icon: Icon, title, children }: Readonly<{
  icon: React.ElementType; title: string; children: React.ReactNode
}>) {
  return (
    <div style={{
      background: 'var(--color-surface)', border: '1px solid var(--color-border)',
      borderRadius: 12, padding: 24,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 8, background: 'rgba(23,118,210,0.1)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon size={18} color="var(--color-brand)" />
        </div>
        <span style={{ fontSize: 15, fontWeight: 600 }}>{title}</span>
      </div>
      {children}
    </div>
  )
}

function Toggle({ checked, onChange, label, description }: Readonly<{
  checked: boolean; onChange: (v: boolean) => void; label: string; description?: string
}>) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '12px 0', borderBottom: '1px solid var(--color-border)',
    }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 500 }}>{label}</div>
        {description && <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>{description}</div>}
      </div>
      <button
        onClick={() => onChange(!checked)}
        style={{
          width: 42, height: 24, borderRadius: 12, border: 'none',
          background: checked ? 'var(--color-brand)' : 'var(--color-surface-2)',
          cursor: 'pointer', position: 'relative', transition: 'background 0.2s',
          flexShrink: 0, marginLeft: 20,
        }}
      >
        <div style={{
          width: 18, height: 18, borderRadius: 9, background: 'white',
          position: 'absolute', top: 3,
          left: checked ? 21 : 3,
          transition: 'left 0.2s',
          boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
        }} />
      </button>
    </div>
  )
}

function FormField({ label, type = 'text', value, onChange, placeholder }: Readonly<{
  label: string; type?: string; value: string; onChange: (v: string) => void; placeholder?: string
}>) {
  const id = `field-${label.replace(/\W+/g, '-').toLowerCase()}`
  return (
    <div style={{ marginBottom: 14 }}>
      <label htmlFor={id} style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>{label}</label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        style={{
          width: '100%', padding: '9px 12px', fontSize: 13,
          border: '1px solid var(--color-border)', borderRadius: 7,
          background: 'var(--color-surface-2)', color: 'var(--color-text)', outline: 'none',
        }}
      />
    </div>
  )
}

/**
 * The Entra certificate a Microsoft connection signs in with: its thumbprint, when it
 * expires, and a one-click rotation. A certificate that lapses silently is the most
 * common reason a dashboard stops updating.
 */
function CertificateStatus({ connection, onRotated }: Readonly<{
  connection: Connection; onRotated: () => void
}>) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  if (connection.config.auth_method !== 'certificate') return null

  const rawThumbprint = connection.config.certificate_thumbprint
  const rawExpires = connection.config.certificate_expires_at
  const thumbprint = typeof rawThumbprint === 'string' ? rawThumbprint : ''
  const expires = typeof rawExpires === 'string' ? rawExpires : ''
  const daysLeft = expires ? Math.ceil((new Date(expires).getTime() - Date.now()) / 86_400_000) : null
  const expired = daysLeft !== null && daysLeft <= 0
  const soon = daysLeft !== null && daysLeft <= 30
  const dayWord = daysLeft === 1 ? 'day' : 'days'

  const rotate = async () => {
    setError('')
    // Validity is chosen per rotation; Entra accepts 1-1095 days, and a year is
    // the default because it is long enough to forget and short enough to matter.
    const answer = window.prompt('New certificate lifetime in days (1-1095):', '365')
    if (answer === null) return
    const days = Number(answer)
    if (!Number.isFinite(days) || days < 1 || days > 1095) {
      setError('Enter a whole number of days between 1 and 1095.')
      return
    }
    setBusy(true)
    try {
      await api.post('/onboarding/microsoft/certificate/rotate', { validity_days: Math.round(days) })
      onRotated()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Could not rotate the certificate.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 4 }}>
      <div style={{ fontFamily: 'monospace' }}>
        {thumbprint ? `Thumbprint ${thumbprint}` : 'Certificate'}
        {expires ? ` · expires ${new Date(expires).toLocaleDateString()}` : ''}
      </div>
      {(soon || expired) && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 2, color: expired ? 'var(--color-high)' : '#D97706' }}>
          <AlertTriangle size={12} />
          {expired
            ? 'This certificate has expired — collection has stopped. Rotate it now.'
            : `Expires in ${daysLeft} ${dayWord} — rotate it before it lapses.`}
        </div>
      )}
      <button
        onClick={rotate}
        disabled={busy}
        style={{
          marginTop: 6, display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 9px',
          fontSize: 11, borderRadius: 6, border: '1px solid var(--color-border)',
          background: 'var(--color-surface-2)', color: 'var(--color-text)',
          cursor: busy ? 'default' : 'pointer',
        }}
      >
        <KeyRound size={11} /> {busy ? 'Rotating…' : 'Rotate certificate'}
      </button>
      {error && <div style={{ color: 'var(--color-high)', marginTop: 4 }}>{error}</div>}
    </div>
  )
}

/**
 * Platforms connected during setup, plus a way to add another one later — the
 * "start with Microsoft 365, add AWS next quarter" path. The Google platforms can
 * share one service account here too, not only in the first-run wizard.
 */
function PlatformConnections() {
  const [connections, setConnections] = useState<Connection[]>([])
  const [platforms, setPlatforms] = useState<Platform[]>([])
  const [adding, setAdding] = useState<string | null>(null)
  const [error, setError] = useState('')

  const load = () => {
    api.get('/onboarding/status').then((r) => {
      setConnections(r.data.connections)
      setPlatforms(r.data.platforms)
    }).catch(() => setError('Could not load platform connections.'))
  }

  useEffect(() => { load() }, [])

  const remove = async (provider: string) => {
    try {
      await api.delete(`/onboarding/connections/${provider}`)
      load()
    } catch { setError('Could not remove that connection.') }
  }

  const connectedIds = new Set(connections.map((c) => c.provider))
  const available = platforms.filter((p) => !connectedIds.has(p.id))
  const googleShared = ['gcp', 'google_workspace'].every((id) => available.some((p) => p.id === id))
  const addingPlatform = available.find((p) => p.id === adding)

  return (
    <Section icon={Plug} title="Platform connections">
      {connections.length === 0 && (
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>No platforms connected yet.</p>
      )}
      {connections.map((c) => (
        <div key={c.id} style={{
          display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12,
          padding: '10px 0', borderBottom: '1px solid var(--color-border)',
        }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 500 }}>{c.display_name || c.provider}</div>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
              {c.provider} · {c.account || 'configured'}
              {c.config.shared_service_account ? ' · shared service account' : ''}
              {c.status !== 'connected' ? ` · ${c.status.replace(/_/g, ' ')}` : ''}
            </div>
            <CertificateStatus connection={c} onRotated={load} />
          </div>
          <button
            onClick={() => remove(c.provider)}
            title={`Disconnect ${c.provider}`}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)' }}
          >
            <Trash2 size={15} />
          </button>
        </div>
      ))}

      {available.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <label htmlFor="add-platform" style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>
            Connect another platform
          </label>
          <select
            id="add-platform"
            value={adding || ''}
            onChange={(e) => setAdding(e.target.value || null)}
            style={{
              padding: '9px 12px', fontSize: 13, borderRadius: 7, width: '100%', maxWidth: 320,
              border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
              color: 'var(--color-text)', cursor: 'pointer',
            }}
          >
            <option value="">Choose a platform…</option>
            {available.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            {googleShared && (
              <option value={GOOGLE_SHARED}>Google Cloud + Workspace — one service account</option>
            )}
          </select>
          {addingPlatform && (
            <div style={{ marginTop: 14 }}>
              <PlatformConnector
                platform={addingPlatform}
                connected={undefined}
                onConnected={() => { setAdding(null); load() }}
              />
            </div>
          )}
          {adding === GOOGLE_SHARED && googleShared && (
            <div style={{ marginTop: 14 }}>
              <GoogleSharedConnector onConnected={() => { setAdding(null); load() }} />
            </div>
          )}
        </div>
      )}
      {error && <p style={{ fontSize: 13, color: 'var(--color-high)', marginTop: 10 }}>{error}</p>}
    </Section>
  )
}

/**
 * The posture snapshot is a JSON document merged into collected data for posture
 * keys Graph cannot expose. Editing it from here removes the need for shell
 * access; the server refuses to create a path that was never configured.
 */
function PostureSnapshotEditor() {
  const { data, refetch } = useQuery({
    queryKey: ['settings', 'posture-snapshot'],
    queryFn: () => api.get('/settings/posture-snapshot').then((r) => r.data),
  })
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (data) setText(JSON.stringify(data.snapshot ?? {}, null, 2))
  }, [data])

  const save = async () => {
    setError('')
    setSaved(false)
    let parsed: unknown
    try {
      parsed = JSON.parse(text || '{}')
    } catch {
      setError('That is not valid JSON. Fix the syntax and save again.')
      return
    }
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      setError('The snapshot must be a JSON object.')
      return
    }
    try {
      await api.put('/settings/posture-snapshot', parsed)
      setSaved(true)
      void refetch()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Could not save the posture snapshot.')
    }
  }

  return (
    <Section icon={FileJson} title="Posture snapshot">
      <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 12 }}>
        JSON values merged into collected data for posture facts no Graph endpoint exposes.
        {data?.configured
          ? ` Stored at ${data.path}.`
          : ' UNIMONITOR_POSTURE_SNAPSHOT is not configured, so this editor is read-only.'}
      </p>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={10}
        spellCheck={false}
        style={{
          width: '100%', padding: 12, fontSize: 12, fontFamily: 'monospace',
          border: '1px solid var(--color-border)', borderRadius: 7,
          background: 'var(--color-surface-2)', color: 'var(--color-text)', outline: 'none',
          resize: 'vertical',
        }}
      />
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 10 }}>
        <button
          onClick={save}
          disabled={!data?.configured}
          style={{
            display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', fontSize: 12,
            background: 'var(--color-brand)', color: 'white', border: 'none', borderRadius: 7,
            cursor: data?.configured ? 'pointer' : 'not-allowed', opacity: data?.configured ? 1 : 0.5,
          }}
        >
          <Save size={13} /> Save snapshot
        </button>
        {saved && <span style={{ fontSize: 12, color: '#10B981' }}>Snapshot saved</span>}
        {error && <span style={{ fontSize: 12, color: 'var(--color-high)' }}>{error}</span>}
      </div>
    </Section>
  )
}

/**
 * SIEM and ticketing connectors are configured with deployment secrets; this
 * panel shows which ones are ready, lets an admin test the wiring and push the
 * current open findings without leaving the product.
 */
function IntegrationsPanel() {
  const { data, refetch } = useQuery({
    queryKey: ['integrations'],
    queryFn: () => api.get('/integrations').then((r) => r.data),
  })
  const [busy, setBusy] = useState('')
  const [result, setResult] = useState('')
  const [severity, setSeverity] = useState('high')

  const act = async (label: string, path: string, body?: unknown) => {
    setBusy(label)
    setResult('')
    try {
      const response = await api.post(path, body)
      const sent = response.data.sent ?? response.data.created
      const errors = response.data.errors ? `, ${response.data.errors} errors` : ''
      setResult(`${label}: ${sent ?? 0} sent${errors}`)
      void refetch()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setResult(`${label}: ${detail || 'failed'}`)
    } finally {
      setBusy('')
    }
  }

  const siem = data?.siem ?? []
  const ticketing = data?.ticketing ?? []

  return (
    <Section icon={Webhook} title="SIEM and ticketing connectors">
      <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 12 }}>
        Connectors are enabled by their deployment secrets. Nothing is sent automatically.
      </div>
      {siem.map((connector: {
        slug: string; name: string; description: string; configured: boolean; missing_settings: string[]
      }) => (
        <div key={connector.slug} style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
          padding: '10px 0', borderBottom: '1px solid var(--color-border)',
        }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 500 }}>{connector.name}</div>
            <div style={{ fontSize: 11, color: connector.configured ? '#10B981' : 'var(--color-text-muted)' }}>
              {connector.configured
                ? 'Ready'
                : `Needs ${connector.missing_settings.join(', ')}`}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              onClick={() => act(`${connector.name} test`, `/integrations/siem/${connector.slug}/test`)}
              disabled={!connector.configured || busy !== ''}
              style={{ fontSize: 11, padding: '5px 9px', borderRadius: 6, border: '1px solid var(--color-border)', background: 'var(--color-surface-2)', color: 'var(--color-text)', cursor: connector.configured ? 'pointer' : 'not-allowed' }}
            >
              Test
            </button>
            <button
              onClick={() => act(connector.name, `/integrations/siem/${connector.slug}/send`, {})}
              disabled={!connector.configured || busy !== ''}
              style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, padding: '5px 9px', borderRadius: 6, border: 'none', background: 'var(--color-brand)', color: 'white', cursor: connector.configured ? 'pointer' : 'not-allowed', opacity: connector.configured ? 1 : 0.5 }}
            >
              <Send size={11} /> Send
            </button>
          </div>
        </div>
      ))}

      <div style={{ marginTop: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>Ticketing sync</div>
        {ticketing.map((provider: { slug: string; name: string; configured: boolean; missing_settings: string[] }) => (
          <div key={provider.slug} style={{ fontSize: 11, color: provider.configured ? '#10B981' : 'var(--color-text-muted)' }}>
            {provider.name}: {provider.configured ? 'ready' : `needs ${provider.missing_settings.join(', ')}`}
          </div>
        ))}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
          <label htmlFor="ticket-severity" style={{ fontSize: 12 }}>Minimum severity</label>
          <select
            id="ticket-severity"
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
            style={{ padding: '6px 9px', fontSize: 12, borderRadius: 6, border: '1px solid var(--color-border)', background: 'var(--color-surface-2)', color: 'var(--color-text)' }}
          >
            {['critical', 'high', 'medium', 'low'].map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
          <button
            onClick={() => act('Ticket sync', '/integrations/ticketing/sync', { min_severity: severity })}
            disabled={busy !== '' || !data?.default_ticketing_provider}
            style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, padding: '6px 10px', borderRadius: 6, border: 'none', background: 'var(--color-brand)', color: 'white', cursor: data?.default_ticketing_provider ? 'pointer' : 'not-allowed', opacity: data?.default_ticketing_provider ? 1 : 0.5 }}
          >
            <Send size={11} /> Sync now
          </button>
        </div>
      </div>
      {result && <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 10 }}>{result}</p>}
    </Section>
  )
}


function AiProvidersPanel() {
  const MASK = '******'
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['ai-status'], queryFn: aiApi.status })
  const [draft, setDraft] = useState({ name: '', base_url: '', model: '', api_key: '' })

  const save = useMutation({
    mutationFn: (providers: { name: string; base_url: string; model: string; api_key: string; enabled: boolean }[]) =>
      aiApi.saveCustom(providers),
    onSuccess: () => {
      setDraft({ name: '', base_url: '', model: '', api_key: '' })
      void qc.invalidateQueries({ queryKey: ['ai-status'] })
    },
  })

  const existing = (data?.custom || []).map(c => ({
    name: c.name, base_url: c.base_url, model: c.model, api_key: c.api_key || MASK, enabled: c.enabled,
  }))

  const add = () => {
    if (!draft.name || !draft.base_url || !draft.model) return
    save.mutate([...existing, { ...draft, enabled: true }])
  }

  return (
    <Section icon={Sparkles} title="AI remediation providers">
      <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 12 }}>
        Guidance is generated from an anonymised prompt (control id, framework, category, severity, state,
        title and description only). Built-in providers are tried in order and the next one is used
        automatically when one is out of quota.
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 14 }}>
        {(data?.providers || []).map(provider => (
          <span key={provider.name} style={{
            fontSize: 11, padding: '2px 8px', borderRadius: 4,
            background: provider.configured ? 'rgba(16,185,129,0.1)' : 'var(--color-surface-2)',
            color: provider.configured ? '#10B981' : 'var(--color-text-muted)',
          }}>
            {provider.name}{provider.free_tier ? ' (free tier)' : ''}{provider.configured ? '' : ' — not configured'}
          </span>
        ))}
        {data?.providers.length === 0 && (
          <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>No built-in provider has a key yet.</span>
        )}
      </div>

      {existing.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
          {existing.map(provider => (
            <div key={provider.name} style={{
              display: 'flex', alignItems: 'center', gap: 10, fontSize: 12,
              padding: '6px 10px', background: 'var(--color-surface-2)', borderRadius: 6,
            }}>
              <strong style={{ minWidth: 110 }}>{provider.name}</strong>
              <span style={{ flex: 1, color: 'var(--color-text-muted)', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {provider.base_url} · {provider.model}
              </span>
              <button
                type="button"
                aria-label={`Remove ${provider.name}`}
                onClick={() => save.mutate(existing.filter(item => item.name !== provider.name))}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#EF4444', padding: 0 }}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr) auto', gap: 8, alignItems: 'end' }}>
        <FormField label="Name" value={draft.name} onChange={value => setDraft({ ...draft, name: value })} placeholder="internal-gw" />
        <FormField label="Base URL" value={draft.base_url} onChange={value => setDraft({ ...draft, base_url: value })} placeholder="https://llm.example.com/v1" />
        <FormField label="Model" value={draft.model} onChange={value => setDraft({ ...draft, model: value })} placeholder="model-name" />
        <FormField label="API key" type="password" value={draft.api_key} onChange={value => setDraft({ ...draft, api_key: value })} placeholder="sk-…" />
        <button
          type="button"
          onClick={add}
          disabled={save.isPending}
          style={{
            padding: '8px 14px', fontSize: 12, background: 'var(--color-brand)', color: 'white',
            border: 'none', borderRadius: 6, cursor: save.isPending ? 'not-allowed' : 'pointer', height: 36,
          }}
        >
          Add
        </button>
      </div>
      {save.isError && (
        <div style={{ fontSize: 11, color: '#EF4444', marginTop: 6 }}>
          Could not save: use lowercase letters, digits or dashes for the name, and an http(s) base URL.
        </div>
      )}
    </Section>
  )
}

export default function SettingsPage() {
  const [saved, setSaved] = useState(false)

  const { data: notifData } = useQuery({
    queryKey: ['settings', 'notifications'],
    queryFn: () => api.get('/settings/notifications').then(r => r.data),
  })

  const defaultSettings: NotificationSettings = {
    smtp_enabled: false,
    smtp_host: '',
    smtp_port: 587,
    smtp_username: '',
    smtp_password: '',
    smtp_to_emails: [],
    teams_webhook_url: '',
    slack_webhook_url: '',
    immediate_alerts: true,
    daily_digest: false,
    weekly_digest: true,
    alert_severity_threshold: 'HIGH',
  }

  const [settings, setSettings] = useState<NotificationSettings>(
    notifData || defaultSettings
  )

  // The query resolves after the first render, so seed the form when it lands
  // instead of leaving the saved values invisible.
  useEffect(() => {
    if (notifData) setSettings(prev => ({ ...prev, ...notifData }))
  }, [notifData])

  const updateSettings = (patch: Partial<NotificationSettings>) => {
    setSettings(prev => ({ ...prev, ...patch }))
  }

  const saveMutation = useMutation({
    mutationFn: () => api.put('/settings/notifications', settings).then(r => r.data),
    onSuccess: () => {
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    },
  })

  const { data: tenantData } = useQuery({
    queryKey: ['settings', 'tenant'],
    queryFn: () => api.get('/settings/tenant').then(r => r.data),
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Settings</h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          Configure notifications, tenant, and system preferences
        </p>
      </div>

      <PlatformConnections />

      <PostureSnapshotEditor />

      <IntegrationsPanel />

      <AiProvidersPanel />

      <BrandingPanel />

      <DelegatedAccessPanel />

      {/* Tenant info */}
      {tenantData && (
        <Section icon={Shield} title="Tenant Information">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            {[
              { label: 'Tenant Name', value: tenantData.name },
              { label: 'Tenant ID', value: tenantData.tenant_id },
              { label: 'Domain', value: tenantData.domain },
              { label: 'Created', value: new Date(tenantData.created_at).toLocaleDateString() },
            ].map(item => (
              <div key={item.label}>
                <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 3, fontWeight: 600 }}>
                  {item.label.toUpperCase()}
                </div>
                <div style={{ fontSize: 13 }}>{item.value || '—'}</div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Notification channels */}
      <Section icon={Bell} title="Notification Settings">
        <Toggle
          checked={settings.immediate_alerts}
          onChange={v => updateSettings({ immediate_alerts: v })}
          label="Immediate Alerts"
          description="Send alerts immediately when critical or high findings are detected"
        />
        <Toggle
          checked={settings.daily_digest}
          onChange={v => updateSettings({ daily_digest: v })}
          label="Daily Digest"
          description="Receive a daily summary of all open findings"
        />
        <Toggle
          checked={settings.weekly_digest}
          onChange={v => updateSettings({ weekly_digest: v })}
          label="Weekly Digest"
          description="Receive a weekly compliance and security summary"
        />
        <div style={{ marginTop: 16 }}>
          <label htmlFor="severity-threshold" style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>
            Alert Severity Threshold
          </label>
          <select
            id="severity-threshold"
            value={settings.alert_severity_threshold}
            onChange={e => updateSettings({ alert_severity_threshold: e.target.value })}
            style={{
              padding: '9px 12px', fontSize: 13, borderRadius: 7, width: 200,
              border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
              color: 'var(--color-text)', cursor: 'pointer',
            }}
          >
            {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
      </Section>

      {/* Email / SMTP */}
      <Section icon={Mail} title="Email (SMTP)">
        <Toggle
          checked={settings.smtp_enabled}
          onChange={v => updateSettings({ smtp_enabled: v })}
          label="Enable Email Notifications"
          description="Send alerts and digests via SMTP email"
        />
        {settings.smtp_enabled && (
          <div style={{ marginTop: 16 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 12 }}>
              <FormField
                label="SMTP Host"
                value={settings.smtp_host || ''}
                onChange={v => updateSettings({ smtp_host: v })}
                placeholder="smtp.office365.com"
              />
              <div>
                <label htmlFor="smtp-port" style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Port</label>
                <input
                  id="smtp-port"
                  type="number"
                  value={settings.smtp_port || 587}
                  onChange={e => updateSettings({ smtp_port: Number.parseInt(e.target.value, 10) })}
                  style={{
                    width: 80, padding: '9px 12px', fontSize: 13,
                    border: '1px solid var(--color-border)', borderRadius: 7,
                    background: 'var(--color-surface-2)', color: 'var(--color-text)', outline: 'none',
                  }}
                />
              </div>
            </div>
            <FormField
              label="SMTP Username"
              value={settings.smtp_username || ''}
              onChange={v => updateSettings({ smtp_username: v })}
              placeholder="alerts@contoso.com"
            />
            <FormField
              label="SMTP Password"
              type="password"
              value={settings.smtp_password || ''}
              onChange={v => updateSettings({ smtp_password: v })}
              placeholder="••••••••"
            />
            <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: -6, marginBottom: 12 }}>
              Stored with the tenant settings and masked when read back. Leave the mask in place to keep it.
            </div>
            <FormField
              label="To Emails (comma-separated)"
              value={(settings.smtp_to_emails || []).join(', ')}
              onChange={v => updateSettings({ smtp_to_emails: v.split(',').map(e => e.trim()).filter(Boolean) })}
              placeholder="security@contoso.com, ciso@contoso.com"
            />
          </div>
        )}
      </Section>

      {/* Teams & Slack */}
      <Section icon={MessageSquare} title="Webhook Channels">
        <FormField
          label="Microsoft Teams Webhook URL"
          value={settings.teams_webhook_url || ''}
          onChange={v => updateSettings({ teams_webhook_url: v })}
          placeholder="https://contoso.webhook.office.com/webhookb2/..."
        />
        <FormField
          label="Slack Webhook URL"
          value={settings.slack_webhook_url || ''}
          onChange={v => updateSettings({ slack_webhook_url: v })}
          placeholder="https://hooks.slack.com/services/..."
        />
      </Section>

      {/* Save button */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending}
          style={{
            padding: '9px 20px', fontSize: 13, background: 'var(--color-brand)',
            color: 'white', border: 'none', borderRadius: 8,
            cursor: saveMutation.isPending ? 'not-allowed' : 'pointer',
            display: 'flex', alignItems: 'center', gap: 8,
            opacity: saveMutation.isPending ? 0.7 : 1,
          }}
        >
          <Save size={14} />
          {saveMutation.isPending ? 'Saving…' : 'Save Settings'}
        </button>
        {saved && (
          <span style={{ fontSize: 13, color: '#10B981' }}>
            ✓ Settings saved
          </span>
        )}
        {saveMutation.isError && (
          <span style={{ fontSize: 13, color: '#EF4444' }}>
            Failed to save. Please try again.
          </span>
        )}
      </div>
    </div>
  )
}
