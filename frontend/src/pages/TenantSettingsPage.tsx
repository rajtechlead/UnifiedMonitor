import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Building2, Plug, Save, Trash2 } from 'lucide-react'
import PlatformConnector, { type Platform } from '../components/PlatformConnector'
import { api, errorDetail, tenantsApi } from '../hooks/useApi'

const panel: React.CSSProperties = {
  background: 'var(--color-surface)', border: '1px solid var(--color-border)',
  borderRadius: 12, padding: 20, display: 'flex', flexDirection: 'column', gap: 12,
}

const input: React.CSSProperties = {
  padding: '8px 10px', fontSize: 13, borderRadius: 6, width: '100%', boxSizing: 'border-box',
  border: '1px solid var(--color-border)', background: 'var(--color-surface-2)', color: 'var(--color-text)',
}

const label: React.CSSProperties = { fontSize: 12, fontWeight: 500, marginBottom: 4, display: 'block' }

export default function TenantSettingsPage() {
  const { tenantId = '' } = useParams()
  const qc = useQueryClient()
  const [message, setMessage] = useState('')
  const [adding, setAdding] = useState('')
  const [draft, setDraft] = useState<Record<string, string> | null>(null)
  const [links, setLinks] = useState<Array<{ label: string; url: string }> | null>(null)

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['tenant-settings', tenantId],
    queryFn: () => tenantsApi.settings(tenantId),
    enabled: Boolean(tenantId),
  })
  const { data: health } = useQuery({
    queryKey: ['tenant-health', tenantId],
    queryFn: () => tenantsApi.health(tenantId),
    enabled: Boolean(tenantId),
  })
  const { data: setup } = useQuery<{ platforms: Platform[] }>({
    queryKey: ['onboarding', 'status'],
    queryFn: () => api.get('/onboarding/status').then(r => r.data),
  })

  const values = draft ?? (data ? {
    portal_name: data.branding.portal_name,
    accent_colour: data.branding.accent_colour,
    logo_url: data.branding.logo_url || '',
    support_email: data.branding.support_email || '',
    collection_interval_minutes: String(data.collection.collection_interval_minutes),
    auto_collection: String(data.collection.auto_collection),
    notes: data.collection.notes,
  } : null)

  const save = useMutation({
    mutationFn: () => tenantsApi.saveSettings(tenantId, {
      portal_name: values?.portal_name,
      accent_colour: values?.accent_colour,
      logo_url: values?.logo_url || null,
      support_email: values?.support_email || null,
      collection_interval_minutes: Number(values?.collection_interval_minutes || 60),
      auto_collection: values?.auto_collection === 'true',
      notes: values?.notes ?? '',
      external_links: (links ?? data?.external_links ?? []).filter(link => link.label.trim() && link.url.trim()),
    }),
    onSuccess: () => {
      setMessage('Settings saved.')
      setDraft(null)
      setLinks(null)
      void qc.invalidateQueries({ queryKey: ['tenant-settings', tenantId] })
      void qc.invalidateQueries({ queryKey: ['tenants', 'rollup'] })
    },
    onError: (err) => setMessage(errorDetail(err, 'Could not save these settings.')),
  })

  const disconnect = useMutation({
    mutationFn: (provider: string) => tenantsApi.disconnect(tenantId, provider),
    onSettled: () => void qc.invalidateQueries({ queryKey: ['tenant-settings', tenantId] }),
  })

  if (isLoading) return <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>Loading client settings…</div>
  if (isError || !data || !values) {
    return (
      <div style={{ ...panel, color: 'var(--color-text-muted)' }}>
        {errorDetail(error, 'This client could not be loaded. Only a platform administrator can open client settings.')}
        <Link to="/msp" style={{ fontSize: 13, color: 'var(--color-brand)' }}>Back to managed tenants</Link>
      </div>
    )
  }

  const connectedProviders = new Set(data.connections.map(connection => connection.provider))
  const available = (setup?.platforms || []).filter(platform => !connectedProviders.has(platform.id))
  const addingPlatform = available.find(platform => platform.id === adding)
  const set = (key: string, value: string) => setDraft({ ...values, [key]: value })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <Link to="/msp" style={{ fontSize: 12, color: 'var(--color-text-muted)', display: 'inline-flex', alignItems: 'center', gap: 4, marginBottom: 8 }}>
          <ArrowLeft size={12} /> Managed tenants
        </Link>
        <h1 style={{ fontSize: 20, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Building2 size={18} /> {data.tenant.display_name || data.tenant.name}
        </h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          {data.tenant.is_active ? 'Active' : 'Suspended'} · directory {data.tenant.entra_tenant_id || '—'}
          {data.tenant.last_collection_at ? ` · last collection ${new Date(data.tenant.last_collection_at).toLocaleString()}` : ' · never collected'}
          {data.tenant.last_collection_status ? ` (${data.tenant.last_collection_status})` : ''}
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
        {[
          { label: 'Runs (24h)', value: health?.total_runs_24h ?? 0 },
          { label: 'Failed (24h)', value: health?.failed_runs_24h ?? 0 },
          { label: 'Graph reachable', value: health?.graph_accessible ? 'yes' : 'no' },
          { label: 'Connected platforms', value: data.connections.length },
        ].map(card => (
          <div key={card.label} style={{ ...panel, textAlign: 'center', padding: 16 }}>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{card.value}</div>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{card.label}</div>
          </div>
        ))}
      </div>

      <div style={panel}>
        <div style={{ fontSize: 14, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Plug size={15} /> Platform connections
        </div>
        <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
          Each client keeps its own credentials in the vault. Connect Microsoft 365, AWS, Google Cloud
          or Google Workspace as needed; collection and findings stay scoped to this client.
        </div>
        {data.connections.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {data.connections.map(connection => (
              <div key={connection.provider} style={{
                display: 'flex', alignItems: 'center', gap: 10, fontSize: 12,
                padding: '8px 10px', background: 'var(--color-surface-2)', borderRadius: 6,
              }}>
                <strong style={{ minWidth: 130 }}>{connection.provider}</strong>
                <span style={{ flex: 1, color: 'var(--color-text-muted)' }}>
                  {connection.display_name || connection.account || '—'} · {connection.status}
                  {connection.last_error ? ` · ${connection.last_error}` : ''}
                </span>
                <button
                  type="button"
                  aria-label={`Remove ${connection.provider}`}
                  onClick={() => { if (window.confirm(`Remove the ${connection.provider} connection for this client?`)) disconnect.mutate(connection.provider) }}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#EF4444', padding: 0 }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>No platform is connected for this client yet.</div>
        )}

        {available.length > 0 && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 4 }}>
            {available.map(platform => (
              <button
                key={platform.id}
                type="button"
                onClick={() => setAdding(adding === platform.id ? '' : platform.id)}
                style={{
                  padding: '6px 12px', fontSize: 12, borderRadius: 7, cursor: 'pointer',
                  border: `1px solid ${adding === platform.id ? platform.colour : 'var(--color-border)'}`,
                  background: 'transparent', color: 'var(--color-text)',
                }}
              >
                Connect {platform.short_name}
              </button>
            ))}
          </div>
        )}

        {addingPlatform && (
          <PlatformConnector
            platform={addingPlatform}
            tenantId={tenantId}
            connected={undefined}
            onConnected={() => {
              setAdding('')
              void qc.invalidateQueries({ queryKey: ['tenant-settings', tenantId] })
            }}
          />
        )}
      </div>

      <div style={panel}>
        <div style={{ fontSize: 14, fontWeight: 600 }}>Branding and portal</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
          <div>
            <label htmlFor="portal_name" style={label}>Portal name</label>
            <input id="portal_name" style={input} value={values.portal_name} onChange={e => set('portal_name', e.target.value)} />
          </div>
          <div>
            <label htmlFor="accent_colour" style={label}>Accent colour</label>
            <input id="accent_colour" style={input} value={values.accent_colour} onChange={e => set('accent_colour', e.target.value)} placeholder="#2563EB" />
          </div>
          <div>
            <label htmlFor="logo_url" style={label}>Logo URL (https or /path)</label>
            <input id="logo_url" style={input} value={values.logo_url} onChange={e => set('logo_url', e.target.value)} placeholder="https://…" />
          </div>
          <div>
            <label htmlFor="support_email" style={label}>Support email</label>
            <input id="support_email" style={input} value={values.support_email} onChange={e => set('support_email', e.target.value)} placeholder="soc@example.com" />
          </div>
        </div>
      </div>

      <div style={panel}>
        <div style={{ fontSize: 14, fontWeight: 600 }}>Client portal and external links</div>
        <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
          Publish a dedicated portal, sub-tenant or runbook link for this client. Links must be public
          https addresses.
        </div>
        {(links ?? data.external_links ?? []).map((link, index) => (
          <div key={`${link.url}-${index}`} style={{ display: 'grid', gridTemplateColumns: '160px 1fr auto', gap: 8, alignItems: 'end' }}>
            <div>
              <label htmlFor={`link-label-${index}`} style={label}>Label</label>
              <input
                id={`link-label-${index}`}
                style={input}
                value={link.label}
                placeholder="Client portal"
                onChange={e => {
                  const next = [...(links ?? data.external_links ?? [])]
                  next[index] = { ...next[index], label: e.target.value }
                  setLinks(next)
                }}
              />
            </div>
            <div>
              <label htmlFor={`link-url-${index}`} style={label}>URL</label>
              <input
                id={`link-url-${index}`}
                style={input}
                value={link.url}
                placeholder="https://portal.example.com/client"
                onChange={e => {
                  const next = [...(links ?? data.external_links ?? [])]
                  next[index] = { ...next[index], url: e.target.value }
                  setLinks(next)
                }}
              />
            </div>
            <button
              type="button"
              aria-label={`Remove ${link.label || 'link'}`}
              onClick={() => setLinks((links ?? data.external_links ?? []).filter((_, position) => position !== index))}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#EF4444', padding: '0 4px 10px' }}
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() => setLinks([...(links ?? data.external_links ?? []), { label: '', url: '' }])}
          style={{ alignSelf: 'flex-start', padding: '6px 12px', fontSize: 12, background: 'transparent', border: '1px solid var(--color-border)', borderRadius: 7, cursor: 'pointer', color: 'var(--color-text)' }}
        >
          Add link
        </button>
      </div>

      <div style={panel}>
        <div style={{ fontSize: 14, fontWeight: 600 }}>Monitoring</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
          <div>
            <label htmlFor="interval" style={label}>Collection interval (minutes)</label>
            <input id="interval" type="number" min={5} max={1440} style={input}
              value={values.collection_interval_minutes}
              onChange={e => set('collection_interval_minutes', e.target.value)} />
          </div>
          <div>
            <label htmlFor="auto" style={label}>Automatic collection</label>
            <select id="auto" style={input} value={values.auto_collection} onChange={e => set('auto_collection', e.target.value)}>
              <option value="true">Enabled</option>
              <option value="false">Paused</option>
            </select>
          </div>
          <div style={{ gridColumn: '1 / -1' }}>
            <label htmlFor="notes" style={label}>Notes for this client</label>
            <textarea id="notes" style={{ ...input, minHeight: 70 }} value={values.notes} onChange={e => set('notes', e.target.value)} />
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            type="button"
            onClick={() => save.mutate()}
            disabled={save.isPending}
            style={{
              padding: '8px 16px', fontSize: 13, background: 'var(--color-brand)', color: 'white',
              border: 'none', borderRadius: 8, cursor: save.isPending ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            <Save size={14} /> {save.isPending ? 'Saving…' : 'Save client settings'}
          </button>
          {message && <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{message}</span>}
        </div>
      </div>
    </div>
  )
}
