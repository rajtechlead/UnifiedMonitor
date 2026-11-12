import { useQuery } from '@tanstack/react-query'
import { dashboardApi, monitoringApi } from '../hooks/useApi'
import { CheckCircle, XCircle, AlertCircle, RefreshCw, Activity } from 'lucide-react'

type CollectorStatus = {
  name: string
  display_name: string
  last_run?: string
  status?: string
  error?: string
  items_collected?: number
}

type ServiceCard = {
  name: string
  status: 'healthy' | 'warning' | 'error' | 'unknown'
  findings: number
  coverage: number
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'healthy' || status === 'success') return <CheckCircle size={16} color="#10B981" />
  if (status === 'error' || status === 'failed') return <XCircle size={16} color="#EF4444" />
  return <AlertCircle size={16} color="#F59E0B" />
}

function CollectorRow({ c, onRun }: { c: CollectorStatus; onRun: (name: string) => void }) {
  return (
    <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
      <td style={{ padding: '10px 12px' }}>
        <div style={{ fontWeight: 500, fontSize: 13 }}>{c.display_name || c.name}</div>
        <div style={{ fontSize: 11, color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>{c.name}</div>
      </td>
      <td style={{ padding: '10px 12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <StatusIcon status={c.status || 'unknown'} />
          <span style={{ fontSize: 13, textTransform: 'capitalize' }}>{c.status || 'unknown'}</span>
        </div>
      </td>
      <td style={{ padding: '10px 12px', fontSize: 13, color: 'var(--color-text-muted)' }}>
        {c.last_run ? new Date(c.last_run).toLocaleString() : '—'}
      </td>
      <td style={{ padding: '10px 12px', fontSize: 13 }}>
        {c.items_collected ?? '—'}
      </td>
      <td style={{ padding: '10px 12px' }}>
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
      </td>
    </tr>
  )
}

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
  const { data: collectors, refetch: refetchCollectors } = useQuery({
    queryKey: ['monitoring', 'collectors'],
    queryFn: monitoringApi.collectors,
  })

  const handleRunCollector = async (name: string) => {
    try {
      await monitoringApi.runCollector(name)
      refetchCollectors()
    } catch {
      // best effort
    }
  }

  const services: ServiceCard[] = security?.services || [
    { name: 'Entra ID', status: 'healthy', findings: 3, coverage: 85 },
    { name: 'Intune', status: 'warning', findings: 7, coverage: 72 },
    { name: 'Defender', status: 'healthy', findings: 2, coverage: 91 },
    { name: 'Purview', status: 'warning', findings: 5, coverage: 68 },
    { name: 'Exchange', status: 'healthy', findings: 1, coverage: 88 },
    { name: 'SharePoint', status: 'healthy', findings: 4, coverage: 76 },
    { name: 'Teams', status: 'healthy', findings: 2, coverage: 80 },
    { name: 'Copilot', status: 'unknown', findings: 0, coverage: 45 },
  ]

  const collectorList: CollectorStatus[] = collectors?.collectors || []
  const systemHealth = health?.status || 'unknown'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Security Dashboard</h1>
          <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
            M365 service health and collector status
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Activity size={16} color={systemHealth === 'healthy' ? '#10B981' : '#F59E0B'} />
          <span style={{ fontSize: 13, fontWeight: 500, textTransform: 'capitalize' }}>
            System: {systemHealth}
          </span>
        </div>
      </div>

      {/* Service health grid */}
      <div>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>M365 Service Coverage</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12 }}>
          {services.map((svc) => (
            <div key={svc.name} style={{
              background: 'var(--color-surface)', border: '1px solid var(--color-border)',
              borderRadius: 10, padding: 16,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>{svc.name}</span>
                <StatusIcon status={svc.status} />
              </div>
              <div style={{ marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>Coverage</span>
                  <span style={{ fontWeight: 600 }}>{svc.coverage}%</span>
                </div>
                <div style={{ height: 4, background: 'var(--color-surface-2)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{
                    height: '100%', width: `${svc.coverage}%`,
                    background: svc.coverage >= 80 ? '#10B981' : svc.coverage >= 60 ? '#F59E0B' : '#EF4444',
                    borderRadius: 2, transition: 'width 0.5s ease',
                  }} />
                </div>
              </div>
              <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
                {svc.findings} open finding{svc.findings !== 1 ? 's' : ''}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Collectors table */}
      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, padding: 20,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 600 }}>Data Collectors</div>
          <button
            onClick={() => { refetchCollectors(); refetchHealth() }}
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
            No collector data available. Run an assessment to populate.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                {['Collector', 'Status', 'Last Run', 'Items', 'Actions'].map(h => (
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
