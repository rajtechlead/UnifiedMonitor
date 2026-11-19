import { useQuery } from '@tanstack/react-query'
import { ShieldAlert, ShieldCheck } from 'lucide-react'
import { dashboardApi } from '../hooks/useApi'

type AuditEntry = {
  id: string
  action: string
  resource_type: string | null
  resource_id: string | null
  actor: string | null
  entry_hash: string | null
  created_at: string
}

type ChainCheck = {
  valid: boolean
  checked: number
  legacy: number
  broken_at: string | null
  reason: string | null
}

export default function AuditPage() {
  const { data: audit, isLoading } = useQuery({
    queryKey: ['dashboard', 'audit'],
    queryFn: dashboardApi.getAudit,
  })
  const { data: chain } = useQuery<ChainCheck>({
    queryKey: ['dashboard', 'audit', 'verify'],
    queryFn: dashboardApi.getAuditVerify,
  })

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300,
        color: 'var(--color-text-muted)' }}>
        Loading audit trail…
      </div>
    )
  }

  const entries: AuditEntry[] = audit?.entries ?? []

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
          Immutable record of platform activity for compliance and forensics
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16 }}>
        {[
          { label: 'Total Audit Events', value: audit?.total ?? 0, color: 'var(--color-brand)' },
          { label: 'Events (24h)', value: audit?.actions_24h ?? 0, color: '#10B981' },
          {
            label: chainLabel,
            value: chain ? `${chain.checked}` : '…',
            color: chain && !chain.valid ? '#EF4444' : '#8B5CF6',
          },
        ].map(card => (
          <div key={card.label} style={{
            background: 'var(--color-surface)', border: '1px solid var(--color-border)',
            borderRadius: 12, padding: 20, textAlign: 'center',
          }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: card.color }}>{card.value}</div>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 4 }}>{card.label}</div>
          </div>
        ))}
      </div>

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

      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, padding: 20,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Recent Events</div>
        {entries.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 32, color: 'var(--color-text-muted)', fontSize: 13 }}>
            No audit events recorded yet.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                {['Timestamp', 'Action', 'Resource', 'Actor', 'Hash'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '8px 12px', fontWeight: 600,
                    color: 'var(--color-text-muted)', fontSize: 12 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '10px 12px', color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
                    {new Date(e.created_at).toLocaleString()}
                  </td>
                  <td style={{ padding: '10px 12px', fontFamily: 'monospace', fontSize: 12 }}>{e.action}</td>
                  <td style={{ padding: '10px 12px', color: 'var(--color-text-muted)' }}>
                    {e.resource_type ? `${e.resource_type}${e.resource_id ? ` · ${e.resource_id.slice(0, 8)}` : ''}` : '—'}
                  </td>
                  <td style={{ padding: '10px 12px', color: 'var(--color-text-muted)', fontFamily: 'monospace', fontSize: 11 }}>
                    {e.actor ?? 'system'}
                  </td>
                  <td style={{ padding: '10px 12px', color: 'var(--color-text-muted)', fontFamily: 'monospace', fontSize: 10 }}>
                    {e.entry_hash ? e.entry_hash.slice(0, 12) : '—'}
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
