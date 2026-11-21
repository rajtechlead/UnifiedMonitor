import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import StatCards from '../components/StatCards'
import { ShieldAlert, ShieldCheck } from 'lucide-react'
import { dashboardApi } from '../hooks/useApi'
import TableHead from '../components/TableHead'

type AuditEntry = {
  id: string
  action: string
  resource_type: string | null
  resource_id: string | null
  actor: string | null
  entry_hash: string | null
  created_at: string
}

type CloudEvent = {
  id: string
  source: string
  action: string
  actor: string
  target: string
  created_at: string
}

type ChainCheck = {
  valid: boolean
  checked: number
  legacy: number
  broken_at: string | null
  reason: string | null
}

const resourceLabel = (entry: AuditEntry) => {
  if (!entry.resource_type) return '—'
  return entry.resource_id ? `${entry.resource_type} · ${entry.resource_id.slice(0, 8)}` : entry.resource_type
}

export default function AuditPage() {
  const [source, setSource] = useState('')
  const { data: audit, isLoading } = useQuery({
    queryKey: ['dashboard', 'audit'],
    queryFn: dashboardApi.getAudit,
  })
  const { data: chain } = useQuery<ChainCheck>({
    queryKey: ['dashboard', 'audit', 'verify'],
    queryFn: dashboardApi.getAuditVerify,
  })

  const entries: AuditEntry[] = audit?.entries ?? []
  const cloudEvents: CloudEvent[] = audit?.cloud_events ?? []
  const sources = Array.from(new Set(cloudEvents.map(event => event.source))).sort((a, b) => a.localeCompare(b))
  const shownEvents = source ? cloudEvents.filter(event => event.source === source) : cloudEvents

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300,
        color: 'var(--color-text-muted)' }}>
        Loading audit trail…
      </div>
    )
  }

  let chainLabel = 'Hash chain'
  let chainMessage = ''
  if (chain) {
    chainLabel = chain.valid ? 'Hash chain valid' : 'Hash chain BROKEN'
    const skipped = chain.legacy ? ` (${chain.legacy} pre-chain entries skipped)` : ''
    chainMessage = chain.valid
      ? `Tamper-evident audit chain verified across ${chain.checked} entries${skipped}.`
      : `Chain broken at entry ${chain.broken_at?.slice(0, 8)}: ${chain.reason}`
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Audit Trail</h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          Platform activity from Microsoft 365, AWS, GCP and Google Workspace, alongside UniMonitor's own
          tamper-evident trail
        </p>
      </div>

      <StatCards
        cards={[
          { label: 'UniMonitor Audit Events', value: audit?.total ?? 0, color: 'var(--color-brand)' },
          { label: 'Events (24h)', value: audit?.actions_24h ?? 0, color: '#10B981' },
          { label: 'Cloud Audit Events', value: cloudEvents.length, color: '#8B5CF6' },
          {
            label: chainLabel,
            value: chain ? `${chain.checked}` : '…',
            color: chain && !chain.valid ? '#EF4444' : '#8B5CF6',
          },
        ]}
      />

      {chain && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, fontSize: 13,
          padding: '12px 16px', borderRadius: 10,
          background: chain.valid ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
          border: `1px solid ${chain.valid ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.35)'}`,
          color: chain.valid ? '#10B981' : '#EF4444',
        }}>
          {chain.valid ? <ShieldCheck size={16} /> : <ShieldAlert size={16} />}
          {chainMessage}
        </div>
      )}

      {/* Platform audit events */}
      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, padding: 20,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, gap: 12 }}>
          <div style={{ fontSize: 14, fontWeight: 600 }}>Cloud Activity</div>
          <select
            value={source}
            onChange={e => setSource(e.target.value)}
            aria-label="Filter cloud activity by platform"
            style={{
              padding: '6px 10px', borderRadius: 6, fontSize: 13,
              border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
              color: 'var(--color-text)',
            }}
          >
            <option value="">All platforms</option>
            {sources.map(item => <option key={item} value={item}>{item}</option>)}
          </select>
        </div>
        {shownEvents.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 32, color: 'var(--color-text-muted)', fontSize: 13 }}>
            No cloud audit events returned. Connect a platform and grant its audit-log read permission.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                          <TableHead headers={['Timestamp', 'Platform', 'Action', 'Actor', 'Target']} cellPadding="8px 12px" background="transparent" />
            <tbody>
              {shownEvents.map(event => (
                <tr key={`${event.id}-${event.created_at}`} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '10px 12px', color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
                    {new Date(event.created_at).toLocaleString()}
                  </td>
                  <td style={{ padding: '10px 12px', fontWeight: 600 }}>{event.source}</td>
                  <td style={{ padding: '10px 12px', fontFamily: 'monospace', fontSize: 12 }}>{event.action}</td>
                  <td style={{ padding: '10px 12px', color: 'var(--color-text-muted)' }}>{event.actor}</td>
                  <td style={{ padding: '10px 12px', color: 'var(--color-text-muted)' }}>{event.target || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* UniMonitor's own trail */}
      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, padding: 20,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>UniMonitor Events</div>
        {entries.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 32, color: 'var(--color-text-muted)', fontSize: 13 }}>
            No audit events recorded yet.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                          <TableHead headers={['Timestamp', 'Action', 'Resource', 'Actor', 'Hash']} cellPadding="8px 12px" background="transparent" />
            <tbody>
              {entries.map(entry => (
                <tr key={entry.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '10px 12px', color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
                    {new Date(entry.created_at).toLocaleString()}
                  </td>
                  <td style={{ padding: '10px 12px', fontFamily: 'monospace', fontSize: 12 }}>{entry.action}</td>
                  <td style={{ padding: '10px 12px', color: 'var(--color-text-muted)' }}>
                    {resourceLabel(entry)}
                  </td>
                  <td style={{ padding: '10px 12px', color: 'var(--color-text-muted)', fontFamily: 'monospace', fontSize: 11 }}>
                    {entry.actor ?? 'system'}
                  </td>
                  <td style={{ padding: '10px 12px', color: 'var(--color-text-muted)', fontFamily: 'monospace', fontSize: 10 }}>
                    {entry.entry_hash ? entry.entry_hash.slice(0, 12) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
