import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { dashboardApi } from '../hooks/useApi'

type FindingCounts = {
  critical: number
  high: number
  medium: number
  low: number
  informational: number
  total: number
}

type StateCounts = {
  implemented: number
  partially_implemented: number
  not_implemented: number
  not_applicable: number
}

type ProviderSummary = {
  provider_id: string
  name: string
  short_name: string
  description: string
  connected: boolean
  controls_total: number
  controls_passed: number
  coverage_pct: number
  scores: { security_score: number; compliance_score: number; risk_score: number }
  finding_counts: FindingCounts
  state_counts: StateCounts
  services: string[]
  collectors: string[]
  credential_settings: string[]
}

type CloudsResponse = {
  providers: ProviderSummary[]
  totals: {
    providers_total: number
    providers_connected: number
    controls_total: number
    controls_passed: number
    coverage_pct: number
    findings_total: number
    critical: number
    high: number
  }
  overall_scores: { security_score: number; compliance_score: number; risk_score: number }
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

export default function CloudDashboard() {
  const { data, isLoading, isError } = useQuery<CloudsResponse>({
    queryKey: ['dashboard', 'clouds'],
    queryFn: dashboardApi.getClouds,
  })

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300,
        color: 'var(--color-text-muted)' }}>
        Loading multi-cloud posture…
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div style={{ ...cardStyle, textAlign: 'center', color: 'var(--color-text-muted)' }}>
        Multi-cloud data is unavailable. Check that the API is reachable.
      </div>
    )
  }

  const { providers, totals, overall_scores } = data
  const chartData = providers.map((p) => ({ name: p.short_name, coverage: Math.round(p.coverage_pct) }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Multi-Cloud Posture</h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          Aggregate view across {totals.providers_total} cloud providers · {totals.controls_total} controls ·
          {' '}{totals.providers_connected} reporting data
        </p>
      </div>

      {/* Aggregate cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16 }}>
        {[
          { label: 'Overall Security Score', value: `${Math.round(overall_scores.security_score)}`, color: scoreColor(overall_scores.security_score) },
          { label: 'Control Coverage', value: `${Math.round(totals.coverage_pct)}%`, color: scoreColor(totals.coverage_pct) },
          { label: 'Controls Passing', value: `${totals.controls_passed}/${totals.controls_total}`, color: 'var(--color-brand)' },
          { label: 'Critical Findings', value: totals.critical, color: '#EF4444' },
          { label: 'High Findings', value: totals.high, color: '#F59E0B' },
        ].map((card) => (
          <div key={card.label} style={{ ...cardStyle, textAlign: 'center' }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: card.color }}>{card.value}</div>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 4 }}>{card.label}</div>
          </div>
        ))}
      </div>

      {/* Coverage comparison */}
      <div style={cardStyle}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Control Coverage by Provider</div>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} stroke="var(--color-text-muted)" />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} stroke="var(--color-text-muted)" />
            <Tooltip
              formatter={(value) => [`${value ?? 0}%`, 'Coverage']}
              contentStyle={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', fontSize: 12 }}
            />
            <Bar dataKey="coverage" radius={[4, 4, 0, 0]}>
              {chartData.map((entry) => (
                <Cell key={entry.name} fill={scoreColor(entry.coverage)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Per-provider cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
        {providers.map((p) => (
          <div key={p.provider_id} style={{ ...cardStyle, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
              <div>
                <div style={{ fontSize: 15, fontWeight: 700 }}>{p.name}</div>
                <div style={{ fontSize: 11, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  {p.provider_id}
                </div>
              </div>
              <span
                style={{
                  marginLeft: 'auto', fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
                  background: p.connected ? 'var(--color-pass-bg)' : 'var(--color-info-bg)',
                  color: p.connected ? 'var(--color-pass)' : 'var(--color-info)',
                }}
              >
                {p.connected ? 'COLLECTING' : 'NO DATA'}
              </span>
            </div>

            <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', minHeight: 32 }}>{p.description}</div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                  {p.controls_passed}/{p.controls_total} controls passing
                </span>
                <span style={{ fontSize: 12, fontWeight: 700, color: scoreColor(p.coverage_pct) }}>
                  {Math.round(p.coverage_pct)}%
                </span>
              </div>
              <div style={{ height: 8, background: 'var(--color-surface-2)', borderRadius: 4, overflow: 'hidden' }}>
                <div style={{ width: `${Math.min(100, p.coverage_pct)}%`, height: '100%', background: scoreColor(p.coverage_pct) }} />
              </div>
            </div>

            <div style={{ display: 'flex', gap: 16, fontSize: 12 }}>
              <span><span style={{ color: '#EF4444', fontWeight: 700 }}>{p.finding_counts.critical}</span> critical</span>
              <span><span style={{ color: '#F59E0B', fontWeight: 700 }}>{p.finding_counts.high}</span> high</span>
              <span><span style={{ color: 'var(--color-text-secondary)', fontWeight: 700 }}>{p.finding_counts.total}</span> findings</span>
            </div>

            <Link
              to={`/clouds/${p.provider_id}`}
              style={{ fontSize: 13, fontWeight: 600, marginTop: 'auto' }}
            >
              Open {p.short_name} dashboard →
            </Link>
          </div>
        ))}
      </div>
    </div>
  )
}
