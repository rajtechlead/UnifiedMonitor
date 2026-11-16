import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '../hooks/useApi'

type SeverityCounts = {
  critical: number; high: number; medium: number; low: number
  informational: number; total: number
}

const SEVERITIES: Array<[keyof SeverityCounts, string, string]> = [
  ['critical', 'Critical', '#EF4444'],
  ['high', 'High', '#F59E0B'],
  ['medium', 'Medium', '#3B82F6'],
  ['low', 'Low', '#10B981'],
  ['informational', 'Informational', '#6B7280'],
]

export default function SocDashboard() {
  const { data: soc, isLoading } = useQuery({
    queryKey: ['dashboard', 'soc'],
    queryFn: dashboardApi.getSoc,
  })

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300,
        color: 'var(--color-text-muted)' }}>
        Loading SOC data…
      </div>
    )
  }

  const alerts: SeverityCounts = soc?.alerts_by_severity ?? {
    critical: 0, high: 0, medium: 0, low: 0, informational: 0, total: 0,
  }
  const maxCount = Math.max(...SEVERITIES.map(([key]) => alerts[key]), 1)

  const kpis = [
    { label: 'Active Alerts', value: soc?.active_alerts ?? 0, color: '#EF4444' },
    { label: 'Acknowledged', value: soc?.acknowledged_alerts ?? 0, color: '#F59E0B' },
    { label: 'Resolved (24h)', value: soc?.resolved_alerts_24h ?? 0, color: '#10B981' },
    {
      label: 'Mean Time to Acknowledge',
      value: soc?.mean_time_to_acknowledge_hours == null ? '—' : `${soc.mean_time_to_acknowledge_hours.toFixed(1)}h`,
      color: 'var(--color-brand)',
    },
    {
      label: 'Mean Time to Resolve',
      value: soc?.mean_time_to_resolve_hours == null ? '—' : `${soc.mean_time_to_resolve_hours.toFixed(1)}h`,
      color: 'var(--color-brand)',
    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>SOC Dashboard</h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          Alerting posture and incident response metrics
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16 }}>
        {kpis.map(card => (
          <div key={card.label} style={{
            background: 'var(--color-surface)', border: '1px solid var(--color-border)',
            borderRadius: 12, padding: 20, textAlign: 'center',
          }}>
            <div style={{ fontSize: 26, fontWeight: 700, color: card.color }}>{card.value}</div>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 4 }}>{card.label}</div>
          </div>
        ))}
      </div>

      {/* Alerts by severity */}
      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, padding: 20,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Alerts by Severity</div>
        {alerts.total === 0 ? (
          <div style={{ textAlign: 'center', padding: 32, color: 'var(--color-text-muted)', fontSize: 13 }}>
            No active alerts.
          </div>
        ) : (
          SEVERITIES.map(([key, label, color]) => (
            <div key={key} style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 4 }}>
                <span>{label}</span>
                <span style={{ fontWeight: 700, color }}>{alerts[key]}</span>
              </div>
              <div style={{ height: 8, background: 'var(--color-surface-2)', borderRadius: 4, overflow: 'hidden' }}>
                <div style={{ width: `${(alerts[key] / maxCount) * 100}%`, height: '100%', background: color }} />
              </div>
            </div>
          ))
        )}
      </div>

      {/* Incident trend */}
      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, padding: 20,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Incident Trend</div>
        {(soc?.incident_trend ?? []).length === 0 ? (
          <div style={{ textAlign: 'center', padding: 32, color: 'var(--color-text-muted)', fontSize: 13 }}>
            No incident history recorded yet.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                {Object.keys(soc.incident_trend[0]).map(k => (
                  <th key={k} style={{ textAlign: 'left', padding: '8px 12px', fontWeight: 600,
                    color: 'var(--color-text-muted)', fontSize: 12, textTransform: 'capitalize' }}>{k}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {soc.incident_trend.map((row: Record<string, unknown>, i: number) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  {Object.keys(soc.incident_trend[0]).map(k => (
                    <td key={k} style={{ padding: '10px 12px' }}>{String(row[k] ?? '—')}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
