import { useQuery } from '@tanstack/react-query'
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
  const critical: TopFinding[] = risk?.critical_risks ?? []
  const cellAt = (likelihood: number, impact: number) =>
    heatmap.find(c => c.likelihood === likelihood && c.impact === impact)?.count ?? 0
  const totalRisks = heatmap.reduce((s, c) => s + c.count, 0)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Risk Dashboard</h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          Risk heatmap and critical exposure across the tenant
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16 }}>
        {[
          { label: 'Overall Risk Score', value: Math.round(risk?.overall_risk_score ?? 0), color: '#F59E0B' },
          { label: 'Findings in Heatmap', value: totalRisks, color: 'var(--color-brand)' },
          { label: 'Critical Risks', value: critical.length, color: '#EF4444' },
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
                      const count = cellAt(likelihood, impact)
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

      {/* Critical risks */}
      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, padding: 20,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Critical Risks</div>
        {critical.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 32, color: 'var(--color-text-muted)', fontSize: 13 }}>
            No critical risks detected.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                {['Title', 'Category', 'Service', 'First Detected'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '8px 12px', fontWeight: 600,
                    color: 'var(--color-text-muted)', fontSize: 12 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {critical.map((f) => (
                <tr key={f.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '10px 12px' }}>{f.title}</td>
                  <td style={{ padding: '10px 12px', color: 'var(--color-text-muted)' }}>{f.category}</td>
                  <td style={{ padding: '10px 12px', color: 'var(--color-text-muted)' }}>{f.service}</td>
                  <td style={{ padding: '10px 12px', color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
                    {new Date(f.first_detected_at).toLocaleDateString()}
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
