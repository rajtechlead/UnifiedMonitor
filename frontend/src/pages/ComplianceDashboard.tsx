import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '../hooks/useApi'
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, Tooltip } from 'recharts'

type FrameworkCoverage = {
  framework_id: string
  framework_name: string
  coverage_pct: number
  controls_total: number
  controls_passed: number
}

const scoreColor = (pct: number) => (pct >= 80 ? '#10B981' : pct >= 60 ? '#F59E0B' : '#EF4444')

function FrameworkBar({ fw }: { fw: FrameworkCoverage }) {
  const pct = Math.round(fw.coverage_pct)
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 500 }}>{fw.framework_name}</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: scoreColor(pct) }}>{pct}%</span>
      </div>
      <div style={{ height: 8, background: 'var(--color-surface-2)', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: scoreColor(pct), transition: 'width 0.5s' }} />
      </div>
      <div style={{ marginTop: 4, fontSize: 11, color: 'var(--color-text-muted)' }}>
        {fw.controls_passed} / {fw.controls_total} mapped controls passing
      </div>
    </div>
  )
}

export default function ComplianceDashboard() {
  const { data: compliance, isLoading } = useQuery({
    queryKey: ['dashboard', 'compliance'],
    queryFn: dashboardApi.getCompliance,
  })

  const frameworks: FrameworkCoverage[] = compliance?.frameworks ?? []
  const overall: number = compliance?.overall_compliance_score ?? 0

  const radarData = frameworks.slice(0, 8).map(fw => ({
    subject: fw.framework_name,
    score: Math.round(fw.coverage_pct),
  }))

  const avgScore = frameworks.length
    ? Math.round(frameworks.reduce((s, f) => s + f.coverage_pct, 0) / frameworks.length)
    : 0

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300,
        color: 'var(--color-text-muted)' }}>
        Loading compliance data…
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Compliance Dashboard</h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          GRC framework coverage across {frameworks.length} active frameworks
        </p>
      </div>

      {/* Summary row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16 }}>
        {[
          { label: 'Overall Compliance Score', value: `${Math.round(overall)}%`, color: scoreColor(overall) },
          { label: 'Avg Framework Coverage', value: `${avgScore}%`, color: scoreColor(avgScore) },
          { label: 'Active Frameworks', value: frameworks.length, color: 'var(--color-brand)' },
          { label: 'At Risk (<50%)', value: frameworks.filter(f => f.coverage_pct < 50).length, color: '#EF4444' },
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

      {/* Radar chart */}
      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, padding: 20,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Compliance Radar</div>
        {radarData.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="var(--color-border)" />
              <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10 }} />
              <Radar dataKey="score" stroke="var(--color-brand)" fill="var(--color-brand)" fillOpacity={0.25} />
              <Tooltip contentStyle={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', fontSize: 12 }} />
            </RadarChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ textAlign: 'center', padding: 60, color: 'var(--color-text-muted)', fontSize: 13 }}>
            Run an assessment to see framework coverage
          </div>
        )}
      </div>

      {/* Framework breakdown */}
      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, padding: 24,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 20 }}>Framework Breakdown</div>
        {frameworks.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 32, color: 'var(--color-text-muted)', fontSize: 13 }}>
            No compliance data yet. Run an assessment to populate framework scores.
          </div>
        ) : (
          frameworks.map((fw) => <FrameworkBar key={fw.framework_id} fw={fw} />)
        )}
      </div>
    </div>
  )
}
