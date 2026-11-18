import { useEffect, useRef, useState } from 'react'
import { CheckCircle, AlertTriangle, ExternalLink, Loader, Download, KeyRound } from 'lucide-react'
import { api } from '../hooks/useApi'

export type PlatformField = {
  name: string
  label: string
  placeholder: string
  required: string
  multiline?: string
}
export type PlatformAuthMethod = { id: string; label: string; description: string }
export type Platform = {
  id: string
  name: string
  short_name: string
  description: string
  colour: string
  automated: boolean
  config_fields: PlatformField[]
  secret_fields: PlatformField[]
  auth_methods: PlatformAuthMethod[]
}
export type Connection = {
  id: string
  provider: string
  account: string
  display_name: string
  status: string
  config: Record<string, unknown>
  last_error: string | null
}

type DeviceCode = {
  device_code: string
  user_code: string
  verification_uri: string
  interval: number
  expires_in: number
}

type CertificateFiles = { name: string; label: string; content: string }
type Certificate = {
  thumbprint: string
  not_after: string
  files: CertificateFiles[]
}
type PendingUpload = {
  certificate: Certificate
  steps: string[]
  error: string
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 11px', fontSize: 13, borderRadius: 7,
  border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
  color: 'var(--color-text)', outline: 'none',
}

function Field({ field, value, onChange }: Readonly<{
  field: PlatformField; value: string; onChange: (v: string) => void
}>) {
  return (
    <label style={{ display: 'block', marginBottom: 10 }}>
      <span style={{ display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 4 }}>
        {field.label}{field.required ? ' *' : ''}
      </span>
      {field.multiline ? (
        <textarea
          value={value}
          placeholder={field.placeholder}
          onChange={(e) => onChange(e.target.value)}
          rows={4}
          style={{ ...inputStyle, fontFamily: 'monospace', fontSize: 11, resize: 'vertical' }}
        />
      ) : (
        <input
          type="text"
          value={value}
          placeholder={field.placeholder}
          onChange={(e) => onChange(e.target.value)}
          style={inputStyle}
        />
      )}
    </label>
  )
}

function AuthMethodPicker({ methods, value, onChange }: Readonly<{
  methods: PlatformAuthMethod[]; value: string; onChange: (id: string) => void
}>) {
  // `shared_service_account` is offered by the wizard's combined Google connector,
  // not by a single platform's form.
  methods = methods.filter((m) => m.id !== 'shared_service_account')
  if (methods.length < 2) return null
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 8, marginBottom: 12 }}>
      {methods.map((m) => {
        const active = m.id === value
        return (
          <button
            key={m.id}
            onClick={() => onChange(m.id)}
            style={{
              textAlign: 'left', padding: 10, borderRadius: 8, cursor: 'pointer',
              border: `1px solid ${active ? 'var(--color-brand)' : 'var(--color-border)'}`,
              background: active ? 'var(--color-brand)14' : 'var(--color-surface-2)',
              color: 'var(--color-text)',
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 600 }}>{m.label}</div>
            <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 3 }}>{m.description}</div>
          </button>
        )
      })}
    </div>
  )
}

function saveFile(name: string, content: string, type = 'text/plain') {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  URL.revokeObjectURL(url)
}

/**
 * One platform's connection UI, shared by the first-run wizard and the settings page.
 * Microsoft 365 signs in once and creates its own app registration; the credential is
 * a generated certificate unless the administrator asks for a client secret. AWS can
 * assume a role instead of using keys, and both Google platforms can share one key.
 */
export default function PlatformConnector({ platform, connected, onConnected }: Readonly<{
  platform: Platform
  connected?: Connection
  onConnected: (connection: Connection) => void
}>) {
  const [values, setValues] = useState<Record<string, string>>({})
  const [authMethod, setAuthMethod] = useState(platform.auth_methods[0]?.id || '')
  const [validityDays, setValidityDays] = useState('365')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [device, setDevice] = useState<DeviceCode | null>(null)
  const [pending, setPending] = useState<PendingUpload | null>(null)
  const [manual, setManual] = useState(false)
  const pollRef = useRef<number | null>(null)

  useEffect(() => () => { if (pollRef.current) window.clearInterval(pollRef.current) }, [])

  const set = (name: string, value: string) => setValues((v) => ({ ...v, [name]: value }))

  const fields = (): PlatformField[] => {
    const secret = platform.secret_fields
    if (platform.id === 'microsoft') {
      return authMethod === 'certificate'
        ? [...platform.config_fields, ...secret.filter((f) => f.name === 'certificate_pem' || f.name === 'private_key_pem')]
        : [...platform.config_fields, ...secret.filter((f) => f.name === 'client_secret')]
    }
    if (platform.id === 'aws') {
      return authMethod === 'iam_role'
        ? [...platform.config_fields, ...secret.filter((f) => f.name === 'external_id')]
        : [...platform.config_fields.filter((f) => f.name !== 'role_arn'), ...secret.filter((f) => f.name !== 'external_id')]
    }
    return [...platform.config_fields, ...platform.secret_fields]
  }

  const payload = () => {
    const body: Record<string, unknown> = {}
    for (const f of fields()) {
      const v = (values[f.name] || '').trim()
      if (v) body[f.name] = v
    }
    if (platform.auth_methods.length > 1 && authMethod) body.auth_method = authMethod
    return body
  }

  const connectManual = async () => {
    setError(''); setBusy(true)
    try {
      const res = await api.post(`/onboarding/connections/${platform.id}`, payload())
      onConnected(res.data.connection)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Could not connect this platform.')
    } finally {
      setBusy(false)
    }
  }

  const startMicrosoft = async () => {
    setError(''); setBusy(true); setPending(null)
    try {
      const res = await api.post('/onboarding/microsoft/device-code')
      const code: DeviceCode = res.data
      setDevice(code)
      pollRef.current = window.setInterval(() => pollMicrosoft(code.device_code), Math.max(code.interval, 5) * 1000)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Could not start the Microsoft sign-in.')
      setBusy(false)
    }
  }

  const pollMicrosoft = async (deviceCode: string) => {
    try {
      const res = await api.post('/onboarding/microsoft/complete', {
        device_code: deviceCode,
        auth_method: authMethod || 'certificate',
        certificate_validity_days: Math.max(1, Number(validityDays) || 365),
      })
      const status = res.data.status
      if (status === 'connected') {
        if (pollRef.current) window.clearInterval(pollRef.current)
        setDevice(null); setBusy(false)
        onConnected(res.data.connection)
      } else if (status === 'pending_certificate_upload') {
        if (pollRef.current) window.clearInterval(pollRef.current)
        setDevice(null); setBusy(false)
        setPending({
          certificate: res.data.certificate,
          steps: res.data.manual_steps || [],
          error: res.data.certificate_error || '',
        })
      } else if (status === 'expired' || status === 'declined') {
        if (pollRef.current) window.clearInterval(pollRef.current)
        setDevice(null); setBusy(false)
        setError(status === 'expired' ? 'The sign-in code expired. Try again.' : 'Sign-in was declined.')
      }
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      if (pollRef.current) window.clearInterval(pollRef.current)
      setDevice(null); setBusy(false)
      setError(detail || 'Microsoft app registration failed. You can enter credentials manually below.')
      setManual(true)
    }
  }

  const checkCertificate = async () => {
    setError(''); setBusy(true)
    try {
      const res = await api.post('/onboarding/microsoft/verify')
      setPending(null)
      onConnected(res.data.connection)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Entra still rejects the certificate. Check that it was uploaded to the UniMonitor app.')
    } finally {
      setBusy(false)
    }
  }

  if (connected?.status === 'connected') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--color-text-muted)' }}>
        <CheckCircle size={16} color="#22c55e" />
        Connected as <strong style={{ color: 'var(--color-text)' }}>{connected.display_name || connected.account}</strong>
      </div>
    )
  }

  return (
    <div>
      {platform.automated && !manual && !pending && (
        <div style={{ marginBottom: 12 }}>
          <AuthMethodPicker methods={platform.auth_methods} value={authMethod} onChange={(id) => { setAuthMethod(id); setValues({}) }} />
          {authMethod === 'certificate' && (
            <label style={{ display: 'block', fontSize: 12, marginBottom: 10 }}>
              <span style={{ display: 'block', fontWeight: 500, marginBottom: 4 }}>Certificate validity (days)</span>
              <input
                type="number" min={1} max={1095} value={validityDays}
                onChange={(e) => setValidityDays(e.target.value)}
                style={{ ...inputStyle, maxWidth: 140 }}
              />
              <span style={{ color: 'var(--color-text-muted)' }}>365 days by default. You can rotate it in Entra later.</span>
            </label>
          )}
          <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 10 }}>
            Sign in as a Global Administrator. UniMonitor creates the Entra app registration, requests the
            read-only Graph permissions, grants admin consent and{' '}
            {authMethod === 'certificate' ? 'uploads a generated certificate' : 'mints a client secret'} for you.
          </p>
          <button
            onClick={startMicrosoft}
            disabled={busy}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 8, padding: '9px 14px',
              borderRadius: 7, border: 'none', cursor: busy ? 'default' : 'pointer',
              background: platform.colour, color: '#fff', fontSize: 13, fontWeight: 600,
            }}
          >
            {busy ? <Loader size={14} className="spin" /> : null}
            {busy ? 'Waiting for sign-in…' : 'Sign in with Microsoft'}
          </button>
          {device && (
            <div style={{ marginTop: 12, padding: 12, borderRadius: 8, background: 'var(--color-surface-2)', fontSize: 13 }}>
              <div>Enter the code <strong style={{ fontFamily: 'monospace', fontSize: 15 }}>{device.user_code}</strong> at</div>
              <a href={device.verification_uri} target="_blank" rel="noreferrer"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: 'var(--color-brand)' }}>
                {device.verification_uri} <ExternalLink size={12} />
              </a>
              <div style={{ color: 'var(--color-text-muted)', marginTop: 6 }}>This page updates when the sign-in completes.</div>
            </div>
          )}
          <button
            onClick={() => setManual(true)}
            style={{ marginTop: 10, background: 'none', border: 'none', color: 'var(--color-text-muted)', fontSize: 12, cursor: 'pointer', padding: 0 }}
          >
            I already have an app registration — enter credentials manually
          </button>
        </div>
      )}

      {pending && (
        <div style={{ padding: 14, borderRadius: 10, border: '1px solid var(--color-border)', background: 'var(--color-surface-2)' }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 13, marginBottom: 10 }}>
            <AlertTriangle size={16} color="var(--color-high)" style={{ flexShrink: 0, marginTop: 1 }} />
            <span>
              The app registration and its permissions are in place, but Entra refused the automatic certificate
              upload{pending.error ? `: ${pending.error}` : '.'} Upload it once by hand and setup can continue.
            </span>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
            {pending.certificate?.files.map((f) => (
              <button
                key={f.name}
                onClick={() => saveFile(f.name, f.content)}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 11px',
                  borderRadius: 7, border: '1px solid var(--color-border)', cursor: 'pointer',
                  background: 'var(--color-surface)', color: 'var(--color-text)', fontSize: 12,
                }}
              >
                <Download size={13} /> {f.label}
              </button>
            ))}
          </div>
          {pending.certificate && (
            <p style={{ fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 10, fontFamily: 'monospace' }}>
              Thumbprint {pending.certificate.thumbprint} · valid until {new Date(pending.certificate.not_after).toLocaleDateString()}
            </p>
          )}
          <ol style={{ fontSize: 12, color: 'var(--color-text-muted)', paddingLeft: 18, marginBottom: 12 }}>
            {pending.steps.map((s) => <li key={s} style={{ marginBottom: 4 }}>{s}</li>)}
          </ol>
          <button
            onClick={checkCertificate}
            disabled={busy}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 8, padding: '9px 14px',
              borderRadius: 7, border: 'none', cursor: busy ? 'default' : 'pointer',
              background: 'var(--color-brand)', color: '#fff', fontSize: 13, fontWeight: 600,
            }}
          >
            <KeyRound size={14} /> {busy ? 'Checking…' : 'Check certificate connectivity'}
          </button>
        </div>
      )}

      {(manual || !platform.automated) && (
        <div>
          <AuthMethodPicker methods={platform.auth_methods} value={authMethod} onChange={(id) => { setAuthMethod(id); setValues({}) }} />
          {fields().map((f) => (
            <Field key={f.name} field={f} value={values[f.name] || ''} onChange={(v) => set(f.name, v)} />
          ))}
          <button
            onClick={connectManual}
            disabled={busy}
            style={{
              marginTop: 4, padding: '9px 14px', borderRadius: 7, border: 'none',
              background: platform.colour, color: '#fff', fontSize: 13, fontWeight: 600,
              cursor: busy ? 'default' : 'pointer',
            }}
          >
            {busy ? 'Verifying…' : 'Connect and verify'}
          </button>
        </div>
      )}

      {error && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginTop: 10, color: 'var(--color-high)', fontSize: 13 }}>
          <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>{error}</span>
        </div>
      )}
    </div>
  )
}

/**
 * One service account for both Google platforms.
 *
 * The administrator creates a single service account, grants it project read access
 * and domain-wide delegation, and pastes one key — instead of maintaining a separate
 * identity (and a separate key to rotate) for Google Cloud and Workspace.
 */
export function GoogleSharedConnector({ onConnected }: Readonly<{
  onConnected: (connection: Connection) => void
}>) {
  const [values, setValues] = useState<Record<string, string>>({ customer_id: 'my_customer' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = (name: string, value: string) => setValues((v) => ({ ...v, [name]: value }))

  const connect = async () => {
    setError(''); setBusy(true)
    try {
      const res = await api.post('/onboarding/connections/google-service-account', {
        project_id: (values.project_id || '').trim(),
        admin_email: (values.admin_email || '').trim(),
        customer_id: (values.customer_id || 'my_customer').trim(),
        credentials_json: values.credentials_json || '',
        providers: ['gcp', 'google_workspace'],
      })
      const first = res.data.connections?.[0]
      if (first) onConnected(first)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Could not connect with that service account.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 12 }}>
        Create one Google service account, grant it read access to the project and domain-wide delegation for the
        Workspace admin scopes, then paste its JSON key once. Both platforms use it.
      </p>
      {[
        { name: 'project_id', label: 'Google Cloud project ID', placeholder: 'my-project', multiline: false },
        { name: 'admin_email', label: 'Workspace administrator email', placeholder: 'admin@example.com', multiline: false },
        { name: 'customer_id', label: 'Customer ID', placeholder: 'my_customer', multiline: false },
        { name: 'credentials_json', label: 'Service-account JSON key', placeholder: 'paste the key file contents', multiline: true },
      ].map((f) => (
        <Field
          key={f.name}
          field={{ name: f.name, label: f.label, placeholder: f.placeholder, required: '', multiline: f.multiline ? '1' : '' }}
          value={values[f.name] || ''}
          onChange={(v) => set(f.name, v)}
        />
      ))}
      <button
        onClick={connect}
        disabled={busy}
        style={{
          padding: '9px 14px', borderRadius: 7, border: 'none', background: '#4285F4',
          color: '#fff', fontSize: 13, fontWeight: 600, cursor: busy ? 'default' : 'pointer',
        }}
      >
        {busy ? 'Verifying…' : 'Connect both with one service account'}
      </button>
      {error && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginTop: 10, color: 'var(--color-high)', fontSize: 13 }}>
          <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>{error}</span>
        </div>
      )}
    </div>
  )
}
