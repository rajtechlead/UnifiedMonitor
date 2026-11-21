import { useQuery } from '@tanstack/react-query'
import { dashboardApi, monitoringApi } from '../hooks/useApi'
import { CheckCircle, XCircle, AlertCircle, RefreshCw, Activity } from 'lucide-react'

type CollectorStatus = {
  name: string
  display_name: string
  provider: string
  connected: boolean
  last_run: string | null
  last_status: string | null
  last_duration_seconds: number | null
}

type SeverityCounts = {
  critical: number
  high: number
  medium: number
  low: number
  informational: number
  total: number
}

function StatusIcon({ status }: Readonly<{ status: string }>) {
  if (status === 'success') return <CheckCircle size={16} color="#10B981" />
  if (status === 'failed' || status === 'error') return <XCircle size={16} color="#EF4444" />
  return <AlertCircle size={16} color="#F59E0B" />
}

function CollectorRow({ c, onRun }: Readonly<{ c: CollectorStatus; onRun: (name: string) => void }>) {
  const status = c.connected === false ? 'not connected' : (c.last_status || 'never run')
  return (
    <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
      <td style={{ padding: '10px 12px' }}>
        <div style={{ fontWeight: 500, fontSize: 13 }}>{c.display_name || c.name}</div>
        <div style={{ fontSize: 11, color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>{c.name}</div>
      </td>
      <td style={{ padding: '10px 12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <StatusIcon status={c.last_status || 'unknown'} />
          <span style={{ fontSize: 13, textTransform: 'capitalize' }}>{status}</span>
        </div>
      </td>
      <td style={{ padding: '10px 12px', fontSize: 13, color: 'var(--color-text-muted)' }}>
        {c.last_run ? new Date(c.last_run).toLocaleString() : '—'}
      </td>
      <td style={{ padding: '10px 12px', fontSize: 13, color: 'var(--color-text-muted)' }}>
        {c.last_duration_seconds != null ? `${c.last_duration_seconds.toFixed(1)}s` : '—'}
      </td>
      <td style={{ padding: '10px 12px' }}>
        {c.connected === false ? (
          <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>Connect in Settings</span>
        ) : (
        <button
          onClick={() => onRun(c.name)}
          style={{
            padding: '4px 10px', fontSize: 12, background: 'transparent',
            border: '1px solid var(--color-brand)', borderRadius: 6,
            color: 'var(--color-brand)', cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 4,
          }}
        >
          <RefreshCw size={12} />
          Run
        </button>
        )}
      </td>
    </tr>
  )
}

const SEVERITIES: { key: keyof SeverityCounts; label: string; colour: string }[] = [
  { key: 'critical', label: 'Critical', colour: '#B91C1C' },
  { key: 'high', label: 'High', colour: '#EF4444' },
  { key: 'medium', label: 'Medium', colour: '#F59E0B' },
  { key: 'low', label: 'Low', colour: '#3B82F6' },
  { key: 'informational', label: 'Informational', colour: '#64748B' },
]

export default function SecurityDashboard() {
  const { data: security } = useQuery({
    queryKey: ['dashboard', 'security'],
    queryFn: dashboardApi.getSecurity,
  })
  const { data: health, refetch: refetchHealth } = useQuery({
    queryKey: ['monitoring', 'health'],
    queryFn: monitoringApi.health,
    refetchInterval: 30000,
  })
  const { data: collectors, refetch: refetchCollectors } = useQuery<CollectorStatus[]>({
    queryKey: ['monitoring', 'collectors'],
    queryFn: monitoringApi.collectors,
  })

  const handleRunCollector = async (name: string) => {
    try {
      await monitoringApi.runCollector(name)
      void refetchCollectors()
    } catch {
      // best effort
    }
  }

  // Real counts from stored findings — this page shows nothing it did not collect.
  const counts: SeverityCounts = security?.finding_counts ?? {
    critical: 0, high: 0, medium: 0, low: 0, informational: 0, total: 0,
  }
  const collectorList: CollectorStatus[] = collectors ?? []
  const systemHealth = health?.status || 'unknown'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Security Dashboard</h1>
          <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
            Open findings and collector status
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Activity size={16} color={systemHealth === 'healthy' ? '#10B981' : '#F59E0B'} />
          <span style={{ fontSize: 13, fontWeight: 500, textTransform: 'capitalize' }}>
            System: {systemHealth}
          </span>
        </div>
      </div>

      {/* Findings by severity */}
      <div>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>
          Open Findings · {counts.total}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12 }}>
          {SEVERITIES.map((severity) => (
            <div key={severity.key} style={{
              background: 'var(--color-surface)', border: '1px solid var(--color-border)',
              borderRadius: 10, padding: 16,
            }}>
              <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{severity.label}</div>
              <div style={{ fontSize: 26, fontWeight: 700, color: severity.colour }}>
                {counts[severity.key]}
              </div>
            </div>
          ))}
        </div>
        {counts.total === 0 && (
          <div style={{ marginTop: 10, fontSize: 12, color: 'var(--color-text-muted)' }}>
            No findings stored yet. Run a collection from the Data Collection page.
          </div>
        )}
      </div>

      {/* Collectors table */}
      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, padding: 20,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 600 }}>Data Collectors</div>
          <button
            onClick={() => { void refetchCollectors(); void refetchHealth() }}
            style={{
              padding: '6px 12px', fontSize: 12, background: 'transparent',
              border: '1px solid var(--color-border)', borderRadius: 6,
              color: 'var(--color-text-muted)', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            <RefreshCw size={12} /> Refresh
          </button>
        </div>
        {collectorList.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 32, color: 'var(--color-text-muted)', fontSize: 13 }}>
            No collector data available. Run a collection to populate.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                {['Collector', 'Status', 'Last Run', 'Duration', 'Actions'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '8px 12px',
                    fontWeight: 600, color: 'var(--color-text-muted)', fontSize: 12 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {collectorList.map((c) => (
                <CollectorRow key={c.name} c={c} onRun={handleRunCollector} />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
