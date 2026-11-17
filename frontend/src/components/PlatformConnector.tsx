import { useEffect, useRef, useState } from 'react'
import { CheckCircle, AlertTriangle, ExternalLink, Loader } from 'lucide-react'
import { api } from '../hooks/useApi'

export type PlatformField = { name: string; label: string; placeholder: string; required: string }
export type Platform = {
  id: string
  name: string
  short_name: string
  description: string
  colour: string
  automated: boolean
  config_fields: PlatformField[]
  secret_fields: PlatformField[]
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

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 11px', fontSize: 13, borderRadius: 7,
  border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
  color: 'var(--color-text)', outline: 'none',
}

function Field({ field, value, onChange }: {
  field: PlatformField; value: string; onChange: (v: string) => void
}) {
  return (
    <label style={{ display: 'block', marginBottom: 10 }}>
      <span style={{ display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 4 }}>
        {field.label}{field.required ? ' *' : ''}
      </span>
      <input
        type="text"
        value={value}
        placeholder={field.placeholder}
        onChange={(e) => onChange(e.target.value)}
        style={inputStyle}
      />
    </label>
  )
}

/**
 * One platform's connection UI, shared by the first-run wizard and the settings page.
 * Microsoft 365 is automated (device sign-in creates the app registration and grants
 * consent); the other platforms ask only for the credentials they cannot create for
 * themselves and validate them against the live API before saving.
 */
export default function PlatformConnector({ platform, connected, onConnected }: {
  platform: Platform
  connected?: Connection
  onConnected: (connection: Connection) => void
}) {
  const [values, setValues] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [device, setDevice] = useState<DeviceCode | null>(null)
  const [manual, setManual] = useState(false)
  const pollRef = useRef<number | null>(null)

  useEffect(() => () => { if (pollRef.current) window.clearInterval(pollRef.current) }, [])

  const set = (name: string, value: string) => setValues((v) => ({ ...v, [name]: value }))

  const payload = () => {
    const body: Record<string, string> = {}
    for (const f of [...platform.config_fields, ...platform.secret_fields]) {
      const v = (values[f.name] || '').trim()
      if (v) body[f.name] = v
    }
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
    setError(''); setBusy(true)
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
      const res = await api.post('/onboarding/microsoft/complete', { device_code: deviceCode })
      const status = res.data.status
      if (status === 'connected') {
        if (pollRef.current) window.clearInterval(pollRef.current)
        setDevice(null); setBusy(false)
        onConnected(res.data.connection)
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

  if (connected) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--color-text-muted)' }}>
        <CheckCircle size={16} color="#22c55e" />
        Connected as <strong style={{ color: 'var(--color-text)' }}>{connected.display_name || connected.account}</strong>
      </div>
    )
  }

  return (
    <div>
      {platform.automated && !manual && (
        <div style={{ marginBottom: 12 }}>
          <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 10 }}>
            Sign in as a Global Administrator. UniMonitor creates the Entra app registration,
            requests the read-only Graph permissions and grants admin consent for you.
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

      {(manual || !platform.automated) && (
        <div>
          {platform.config_fields.map((f) => (
            <Field key={f.name} field={f} value={values[f.name] || ''} onChange={(v) => set(f.name, v)} />
          ))}
          {platform.secret_fields.map((f) => (
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
