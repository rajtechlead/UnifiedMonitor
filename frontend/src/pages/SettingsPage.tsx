import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { api } from '../hooks/useApi'
import { Save, Bell, Mail, Users, MessageSquare, Shield } from 'lucide-react'

type NotificationSettings = {
  smtp_enabled: boolean
  smtp_host?: string
  smtp_port?: number
  smtp_username?: string
  smtp_to_emails?: string[]
  teams_webhook_url?: string
  slack_webhook_url?: string
  immediate_alerts: boolean
  daily_digest: boolean
  weekly_digest: boolean
  alert_severity_threshold: string
}

function Section({ icon: Icon, title, children }: {
  icon: React.ElementType; title: string; children: React.ReactNode
}) {
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

function Toggle({ checked, onChange, label, description }: {
  checked: boolean; onChange: (v: boolean) => void; label: string; description?: string
}) {
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

function FormField({ label, type = 'text', value, onChange, placeholder }: {
  label: string; type?: string; value: string; onChange: (v: string) => void; placeholder?: string
}) {
  return (
    <div style={{ marginBottom: 14 }}>
      <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>{label}</label>
      <input
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
          <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>
            Alert Severity Threshold
          </label>
          <select
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
                <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Port</label>
                <input
                  type="number"
                  value={settings.smtp_port || 587}
                  onChange={e => updateSettings({ smtp_port: parseInt(e.target.value) })}
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
