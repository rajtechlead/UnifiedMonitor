import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../hooks/useApi'

type RollupRow = {
  tenant_id: string
  name: string
  display_name: string | null
  is_active: boolean
  last_collection_at: string | null
  last_collection_status: string | null
  security_score: number
  compliance_score: number
  risk_score: number
  open_findings: number
  critical: number
  high: number
  medium: number
  suppressed: number
  coverage_pct: number
  weakest_framework_name: string | null
  weakest_framework_pct: number | null
}

type RollupResponse = {
  tenants: RollupRow[]
  totals: {
    tenants: number
    mean_security_score: number
    mean_compliance_score: number
    open_findings: number
    critical: number
    high: number
    coverage_pct: number
    collection_failures: number
  }
}

const scoreColor = (pct: number) => {
  if (pct >= 80) return '#10B981'
  if (pct >= 60) return '#F59E0B'
  return '#EF4444'
}

const cardStyle = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  borderRadius: 12,
  padding: 20,
}

const inputStyle: React.CSSProperties = {
  padding: '7px 10px', fontSize: 13, borderRadius: 6,
  border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
  color: 'var(--color-text)', width: '100%', boxSizing: 'border-box',
}

function TenantLifecycle() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [form, setForm] = useState({ name: '', display_name: '', entra_tenant_id: '' })
  const [error, setError] = useState('')

  const refresh = () => void qc.invalidateQueries({ queryKey: ['tenants', 'rollup'] })
  const create = useMutation({
    mutationFn: () => api.post('/tenants', form).then(r => r.data),
    onSuccess: (tenant: { id: string }) => {
      setForm({ name: '', display_name: '', entra_tenant_id: '' })
      setError('')
      refresh()
      // Onboarding continues on the client's own page: connect Microsoft, AWS,
      // Google Cloud, Workspace or Okta with that client's administrator.
      navigate(`/tenants/${tenant.id}`)
    },
    onError: () => setError('Could not add the client. The name must be unique; the directory id is optional.'),
  })

  const update = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      api.put(`/tenants/${id}`, { is_active: isActive }).then(r => r.data),
    onSettled: refresh,
  })

  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/tenants/${id}`),
    onSettled: refresh,
  })

  const required = form.name && form.display_name

  return (
    <div style={{ ...cardStyle, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div>
        <div style={{ fontSize: 14, fontWeight: 600 }}>Client lifecycle</div>
        <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
          Add a client, then connect its platforms on the client's own page. Suspend/activate and
          remove are per row below.
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8 }}>
        {([
          ['name', 'Client name (slug)'],
          ['display_name', 'Display name'],
          ['entra_tenant_id', 'Entra tenant id (Microsoft clients, optional)'],
        ] as const).map(([key, label]) => (
          <input
            key={key}
            value={form[key]}
            onChange={e => setForm(prev => ({ ...prev, [key]: e.target.value }))}
            placeholder={label}
            aria-label={label}
            style={inputStyle}
          />
        ))}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          type="button"
          onClick={() => create.mutate()}
          disabled={!required || create.isPending}
          style={{
            padding: '8px 16px', fontSize: 13, background: 'var(--color-brand)', color: 'white',
            border: 'none', borderRadius: 8, cursor: !required || create.isPending ? 'not-allowed' : 'pointer',
            opacity: !required || create.isPending ? 0.6 : 1,
          }}
        >
          {create.isPending ? 'Adding…' : 'Add client'}
        </button>
        {error && <span style={{ fontSize: 12, color: '#EF4444' }}>{error}</span>}
      </div>

      <TenantTable onToggle={(id, isActive) => update.mutate({ id, isActive })} onDelete={(id) => remove.mutate(id)} pending={update.isPending || remove.isPending} />
    </div>
  )
}

function TenantTable({ onToggle, onDelete, pending }: Readonly<{
  onToggle: (id: string, isActive: boolean) => void
  onDelete: (id: string) => void
  pending: boolean
}>) {
  const { data } = useQuery<{ items: Array<{ id: string; name: string; display_name: string | null; is_active: boolean }> }>({
    queryKey: ['tenants', 'admin-list'],
    queryFn: () => api.get('/tenants', { params: { page_size: 100 } }).then(r => r.data),
  })

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
      <thead>
        <tr style={{ textAlign: 'left', color: 'var(--color-text-muted)', fontSize: 11, textTransform: 'uppercase' }}>
          {['Tenant', 'Status', ''].map(heading => (
            <th key={heading} style={{ padding: '8px 10px', borderTop: '1px solid var(--color-border)', fontWeight: 600 }}>{heading}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {(data?.items ?? []).map(tenant => (
          <tr key={tenant.id} style={{ borderTop: '1px solid var(--color-border)' }}>
            <td style={{ padding: '8px 10px' }}>{tenant.display_name || tenant.name}</td>
            <td style={{ padding: '8px 10px', color: tenant.is_active ? '#10B981' : 'var(--color-text-muted)' }}>
              {tenant.is_active ? 'active' : 'suspended'}
            </td>
            <td style={{ padding: '8px 10px', display: 'flex', gap: 8 }}>
              <Link
                to={`/tenants/${tenant.id}`}
                style={{ padding: '4px 10px', fontSize: 11, borderRadius: 6, border: '1px solid var(--color-border)', background: 'var(--color-surface-2)', color: 'var(--color-brand)', textDecoration: 'none' }}
              >
                Settings
              </Link>
              <button
                type="button"
                disabled={pending}
                onClick={() => onToggle(tenant.id, !tenant.is_active)}
                style={{ padding: '4px 10px', fontSize: 11, borderRadius: 6, cursor: 'pointer', border: '1px solid var(--color-border)', background: 'var(--color-surface-2)', color: 'var(--color-text)' }}
              >
                {tenant.is_active ? 'Suspend' : 'Activate'}
              </button>
              <button
                type="button"
                disabled={pending}
                onClick={() => { if (window.confirm(`Remove ${tenant.display_name || tenant.name}? Findings and history are retained.`)) onDelete(tenant.id) }}
                style={{ padding: '4px 10px', fontSize: 11, borderRadius: 6, cursor: 'pointer', border: '1px solid #EF4444', background: 'transparent', color: '#EF4444' }}
              >
                Remove
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function MspPage() {
  const { data, isLoading, isError } = useQuery<RollupResponse>({
    queryKey: ['tenants', 'rollup'],
    queryFn: () => api.get('/tenants/rollup').then((r) => r.data),
  })

  if (isLoading) {
    return <div style={{ ...cardStyle, color: 'var(--color-text-muted)' }}>Loading managed tenants…</div>
  }

  if (isError || !data) {
    return (
      <div style={{ ...cardStyle, color: 'var(--color-text-muted)' }}>
        The rollup is only available to administrators. Check that you are signed in as an admin.
      </div>
    )
  }

  const { tenants, totals } = data

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Managed tenants</h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          Cross-tenant posture for every active client · {totals.tenants} tenants ·{' '}
          {totals.collection_failures} collection failure{totals.collection_failures === 1 ? '' : 's'}
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 16 }}>
        {[
          { label: 'Mean security score', value: Math.round(totals.mean_security_score), color: scoreColor(totals.mean_security_score) },
          { label: 'Mean compliance', value: Math.round(totals.mean_compliance_score), color: scoreColor(totals.mean_compliance_score) },
          { label: 'Open findings', value: totals.open_findings, color: 'var(--color-brand)' },
          { label: 'Critical open', value: totals.critical, color: '#EF4444' },
          { label: 'High open', value: totals.high, color: '#F59E0B' },
          { label: 'Mean framework coverage', value: `${Math.round(totals.coverage_pct)}%`, color: scoreColor(totals.coverage_pct) },
        ].map((card) => (
          <div key={card.label} style={{ ...cardStyle, textAlign: 'center' }}>
            <div style={{ fontSize: 26, fontWeight: 700, color: card.color }}>{card.value}</div>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 4 }}>{card.label}</div>
          </div>
        ))}
      </div>

      <TenantLifecycle />

      <div style={{ ...cardStyle, padding: 0, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ textAlign: 'left', color: 'var(--color-text-muted)', fontSize: 11, textTransform: 'uppercase' }}>
              {['Tenant', 'Security', 'Compliance', 'Coverage', 'Open', 'Crit', 'High', 'Weakest framework', 'Last collection'].map((heading) => (
                <th key={heading} style={{ padding: '12px 16px', borderBottom: '1px solid var(--color-border)', fontWeight: 600 }}>
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tenants.length === 0 && (
              <tr>
                <td colSpan={9} style={{ padding: 20, color: 'var(--color-text-muted)' }}>
                  No active tenants yet. Add one under Settings → Platform connections.
                </td>
              </tr>
            )}
            {tenants.map((row) => (
              <tr key={row.tenant_id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                <td style={{ padding: '12px 16px' }}>
                  <div style={{ fontWeight: 600 }}>{row.display_name || row.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{row.tenant_id}</div>
                </td>
                <td style={{ padding: '12px 16px', color: scoreColor(row.security_score), fontWeight: 600 }}>
                  {Math.round(row.security_score)}
                </td>
                <td style={{ padding: '12px 16px' }}>{Math.round(row.compliance_score)}</td>
                <td style={{ padding: '12px 16px' }}>{Math.round(row.coverage_pct)}%</td>
                <td style={{ padding: '12px 16px' }}>{row.open_findings}</td>
                <td style={{ padding: '12px 16px', color: row.critical ? '#EF4444' : undefined }}>{row.critical}</td>
                <td style={{ padding: '12px 16px', color: row.high ? '#F59E0B' : undefined }}>{row.high}</td>
                <td style={{ padding: '12px 16px' }}>
                  {row.weakest_framework_name
                    ? `${row.weakest_framework_name} (${Math.round(row.weakest_framework_pct ?? 0)}%)`
                    : '—'}
                </td>
                <td style={{ padding: '12px 16px', color: 'var(--color-text-muted)', fontSize: 12 }}>
                  {row.last_collection_at ? new Date(row.last_collection_at).toLocaleString() : 'never'}
                  {row.last_collection_status ? ` · ${row.last_collection_status}` : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
