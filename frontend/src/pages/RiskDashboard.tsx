import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { dashboardApi } from '../hooks/useApi'

type RiskCell = { likelihood: number; impact: number; count: number; findings: string[] }
type TopFinding = {
  id: string; title: string; severity: string
  category: string; service: string; first_detected_at: string
}

const LEVELS = [1, 2, 3, 4, 5]
const cellColor = (count: number) =>
  count === 0 ? 'var(--color-surface-2)'
    : count <= 1 ? '#FDE68A'
      : count <= 3 ? '#F59E0B'
        : count <= 6 ? '#F97316' : '#EF4444'

export default function RiskDashboard() {
  const { data: risk, isLoading } = useQuery({
    queryKey: ['dashboard', 'risk'],
    queryFn: dashboardApi.getRisk,
  })

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300,
        color: 'var(--color-text-muted)' }}>
        Loading risk data…
      </div>
    )
  }

  const heatmap: RiskCell[] = risk?.heatmap ?? []
  const openRisks: TopFinding[] = risk?.risks ?? risk?.critical_risks ?? []
  const criticalCount = openRisks.filter(r => r.severity === 'critical').length
  const totalRisks = heatmap.reduce((s, c) => s + c.count, 0)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Risk Dashboard</h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          Risk heatmap and every open risk across the tenant
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16 }}>
        {[
          { label: 'Overall Risk Score', value: Math.round(risk?.overall_risk_score ?? 0), color: '#F59E0B' },
          { label: 'Findings in Heatmap', value: totalRisks, color: 'var(--color-brand)' },
          { label: 'Open Risks', value: openRisks.length, color: '#F97316' },
          { label: 'Critical Risks', value: criticalCount, color: '#EF4444' },
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

      {/* Heatmap */}
      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, padding: 20,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Risk Heatmap</div>
        {heatmap.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--color-text-muted)', fontSize: 13 }}>
            No heatmap data yet. Run an assessment to populate.
          </div>
        ) : (
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ display: 'flex', flexDirection: 'column-reverse', justifyContent: 'space-around',
              fontSize: 11, color: 'var(--color-text-muted)', paddingBottom: 22 }}>
              {LEVELS.map(l => <span key={l}>Impact {l}</span>)}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', flexDirection: 'column-reverse', gap: 6 }}>
                {LEVELS.map(impact => (
                  <div key={impact} style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6 }}>
                    {LEVELS.map(likelihood => {
                      const cell = heatmap.find(c => c.likelihood === likelihood && c.impact === impact)
                      const count = cell?.count ?? 0
                      return (
                        <div key={likelihood} title={`Likelihood ${likelihood} × Impact ${impact}: ${count}`} style={{
                          height: 52, borderRadius: 6, background: cellColor(count),
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 13, fontWeight: 600, color: count >= 2 ? '#1F2937' : 'var(--color-text-muted)',
                        }}>
                          {count > 0 ? count : ''}
                        </div>
                      )
                    })}
                  </div>
                ))}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6, marginTop: 8,
                fontSize: 11, color: 'var(--color-text-muted)', textAlign: 'center' }}>
                {LEVELS.map(l => <span key={l}>Likelihood {l}</span>)}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Every open risk */}
      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, padding: 20,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Open Risks</div>
        {openRisks.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 32, color: 'var(--color-text-muted)', fontSize: 13 }}>
            No open risks detected.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                {['Title', 'Severity', 'Category', 'Service', 'First Detected', ''].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '8px 12px', fontWeight: 600,
                    color: 'var(--color-text-muted)', fontSize: 12 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {openRisks.map((risk) => (
                <tr key={risk.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '10px 12px' }}>
                    <Link to={`/findings?finding=${risk.id}`}>{risk.title}</Link>
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <span className={`severity-chip severity-${risk.severity?.toLowerCase()}`}>{risk.severity}</span>
                  </td>
                  <td style={{ padding: '10px 12px', color: 'var(--color-text-muted)' }}>{risk.category}</td>
                  <td style={{ padding: '10px 12px', color: 'var(--color-text-muted)' }}>{risk.service}</td>
                  <td style={{ padding: '10px 12px', color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
                    {new Date(risk.first_detected_at).toLocaleDateString()}
                  </td>
                  <td style={{ padding: '10px 12px', whiteSpace: 'nowrap' }}>
                    <Link to={`/findings?finding=${risk.id}`} style={{ fontSize: 12 }}>
                      Guidance &amp; remediation →
                    </Link>
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
