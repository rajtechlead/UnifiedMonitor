import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { api, dashboardApi } from '../hooks/useApi'

type CloudRiskRow = {
  provider_id: string
  name: string
  short_name: string
  colour: string
  connected: boolean
  security_score: number
  coverage_pct: number
  critical: number
  high: number
  findings_total: number
}

type CisoRiskItem = {
  id: string
  title: string
  severity: string
  state: string
  provider_id: string
  provider_name: string
  colour: string
  service: string
  risk_score: number
  first_detected_at: string
}

type FrameworkRow = {
  framework_id: string
  framework_name: string
  coverage_pct: number
  controls_total: number
  controls_passed: number
}

type TrendPoint = { date: string; security_score: number; compliance_score: number; risk_score: number }

type MttrRow = {
  severity: string
  resolved: number
  mean_hours: number | null
  median_hours: number | null
  p90_hours: number | null
  sla_hours: number | null
}

type SlaRow = { severity: string; open: number; breached: number; sla_hours: number | null; oldest_hours: number | null }

type TrendsResponse = { remediation: { window_days: number; mttr: MttrRow[]; open_sla: SlaRow[] } }

type CisoResponse = {
  scores: { security_score: number; compliance_score: number; risk_score: number }
  severity_totals: { critical: number; high: number; medium: number; low: number; informational: number; total: number }
  state_totals: { implemented: number; partially_implemented: number; not_implemented: number; not_applicable: number }
  open_findings: number
  suppressed_findings: number
  clouds: CloudRiskRow[]
  top_risks: CisoRiskItem[]
  weakest_frameworks: FrameworkRow[]
  strongest_frameworks: FrameworkRow[]
  coverage_trend: TrendPoint[]
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

function FrameworkCoverageList({ rows, empty }: Readonly<{ rows: FrameworkRow[]; empty: string }>) {
  if (rows.length === 0) {
    return <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>{empty}</div>
  }
  return rows.map((fw) => (
    <div key={fw.framework_id} style={{ marginBottom: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <Link to={`/frameworks/${fw.framework_id}`} style={{ fontSize: 13, fontWeight: 500, color: 'inherit' }}>
          {fw.framework_name}
        </Link>
        <span style={{ fontSize: 13, fontWeight: 700, color: scoreColor(fw.coverage_pct) }}>
          {Math.round(fw.coverage_pct)}%
        </span>
      </div>
      <div style={{ height: 8, background: 'var(--color-surface-2)', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ width: `${Math.min(100, fw.coverage_pct)}%`, height: '100%', background: scoreColor(fw.coverage_pct) }} />
      </div>
      <div style={{ marginTop: 4, fontSize: 11, color: 'var(--color-text-muted)' }}>
        {fw.controls_passed}/{fw.controls_total} controls passing
      </div>
    </div>
  ))
}

export default function CisoDashboard() {
  const { data, isLoading, isError } = useQuery<CisoResponse>({
    queryKey: ['dashboard', 'ciso'],
    queryFn: dashboardApi.getCiso,
  })

  const { data: trends } = useQuery<TrendsResponse>({
    queryKey: ['dashboard', 'trends', 90],
    queryFn: () => api.get('/dashboard/trends', { params: { window_days: 90 } }).then((r) => r.data),
  })

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300,
        color: 'var(--color-text-muted)' }}>
        Loading CISO view…
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div style={{ ...cardStyle, textAlign: 'center', color: 'var(--color-text-muted)' }}>
        The CISO view is unavailable. Check that the API is reachable.
      </div>
    )
  }

  const {
    scores, severity_totals, state_totals, clouds, top_risks,
    weakest_frameworks, strongest_frameworks, coverage_trend,
  } = data
  const reporting = clouds.filter((c) => c.connected)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>CISO Dashboard</h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          Residual risk across {clouds.length} cloud providers · {reporting.length} reporting ·
          {' '}{data.open_findings} open findings
        </p>
      </div>

      {/* Board-level KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 16 }}>
        {[
          { label: 'Security Posture', value: Math.round(scores.security_score), color: scoreColor(scores.security_score), suffix: '/100' },
          { label: 'Compliance', value: Math.round(scores.compliance_score), color: scoreColor(scores.compliance_score), suffix: '/100' },
          { label: 'Risk Score', value: Math.round(scores.risk_score), color: scoreColor(scores.risk_score), suffix: '/100' },
          { label: 'Critical Open', value: severity_totals.critical, color: '#EF4444' },
          { label: 'High Open', value: severity_totals.high, color: '#F59E0B' },
          { label: 'Accepted / Suppressed', value: data.suppressed_findings, color: 'var(--color-info)' },
        ].map((card) => (
          <div key={card.label} style={{ ...cardStyle, textAlign: 'center' }}>
            <div style={{ fontSize: 26, fontWeight: 700, color: card.color }}>
              {card.value}{card.suffix && <span style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>{card.suffix}</span>}
            </div>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 4 }}>{card.label}</div>
          </div>
        ))}
      </div>

      {/* Remediation SLA: how long fixes actually take, and what is overdue */}
      {trends?.remediation && (
        <div style={cardStyle}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 12 }}>
            <span style={{ fontSize: 14, fontWeight: 600 }}>Remediation SLA</span>
            <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
              last {trends.remediation.window_days} days
            </span>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--color-text-muted)', fontSize: 10, textTransform: 'uppercase' }}>
                {['Severity', 'Resolved', 'Mean', 'Median', 'P90', 'Open past SLA'].map((heading) => (
                  <th key={heading} style={{ padding: '6px 8px', borderBottom: '1px solid var(--color-border)' }}>{heading}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trends.remediation.mttr.map((row) => {
                const sla = trends.remediation.open_sla.find((item) => item.severity === row.severity)
                const hours = (value: number | null) => (value === null ? '—' : `${Math.round(value)}h`)
                return (
                  <tr key={row.severity} style={{ borderBottom: '1px solid var(--color-border)' }}>
                    <td style={{ padding: '6px 8px', textTransform: 'capitalize' }}>{row.severity}</td>
                    <td style={{ padding: '6px 8px' }}>{row.resolved}</td>
                    <td style={{ padding: '6px 8px' }}>{hours(row.mean_hours)}</td>
                    <td style={{ padding: '6px 8px' }}>{hours(row.median_hours)}</td>
                    <td style={{ padding: '6px 8px' }}>{hours(row.p90_hours)}</td>
                    <td style={{ padding: '6px 8px', color: sla?.breached ? '#EF4444' : 'var(--color-text-muted)' }}>
                      {sla ? `${sla.breached} of ${sla.open}` : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Cloud exposure */}
      <div style={cardStyle}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 14 }}>Exposure by Cloud</div>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ textAlign: 'left', color: 'var(--color-text-muted)', fontSize: 11, textTransform: 'uppercase' }}>
              <th style={{ padding: '6px 8px' }}>Provider</th>
              <th style={{ padding: '6px 8px' }}>Score</th>
              <th style={{ padding: '6px 8px' }}>Coverage</th>
              <th style={{ padding: '6px 8px' }}>Critical</th>
              <th style={{ padding: '6px 8px' }}>High</th>
              <th style={{ padding: '6px 8px' }}>Findings</th>
              <th style={{ padding: '6px 8px' }} />
            </tr>
          </thead>
          <tbody>
            {clouds.map((c) => (
              <tr key={c.provider_id} style={{ borderTop: '1px solid var(--color-border)' }}>
                <td style={{ padding: '8px', fontWeight: 600 }}>
                  <span style={{
                    display: 'inline-block', width: 8, height: 8, borderRadius: 4,
                    background: c.colour, marginRight: 8,
                  }} />
                  {c.name}
                  {!c.connected && (
                    <span style={{ marginLeft: 8, fontSize: 10, color: 'var(--color-text-muted)' }}>NO DATA</span>
                  )}
                </td>
                <td style={{ padding: '8px', fontWeight: 700, color: scoreColor(c.security_score) }}>
                  {Math.round(c.security_score)}
                </td>
                <td style={{ padding: '8px' }}>{Math.round(c.coverage_pct)}%</td>
                <td style={{ padding: '8px', color: c.critical ? '#EF4444' : 'var(--color-text-muted)', fontWeight: 600 }}>{c.critical}</td>
                <td style={{ padding: '8px', color: c.high ? '#F59E0B' : 'var(--color-text-muted)', fontWeight: 600 }}>{c.high}</td>
                <td style={{ padding: '8px', color: 'var(--color-text-secondary)' }}>{c.findings_total}</td>
                <td style={{ padding: '8px' }}>
                  <Link to={`/clouds/${c.provider_id}`} style={{ fontSize: 12 }}>View →</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 16 }}>
        {/* Top risks */}
        <div style={cardStyle}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Top Risks to Act On</div>
          {top_risks.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>No open risks. Run an assessment to populate.</div>
          ) : (
            top_risks.map((r) => (
              <div key={r.id} style={{
                display: 'flex', gap: 10, alignItems: 'flex-start',
                padding: '8px 0', borderTop: '1px solid var(--color-border)',
              }}>
                <span className={`severity-chip severity-${r.severity === 'informational' ? 'info' : r.severity}`}>
                  {r.severity}
                </span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{r.title}</div>
                  <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
                    <span style={{ color: r.colour, fontWeight: 600 }}>{r.provider_name}</span>
                    {' · '}{r.service} · risk {r.risk_score}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Weakest and strongest frameworks, so a board sees what holds up */}
        <div style={cardStyle}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Weakest Frameworks</div>
          <FrameworkCoverageList rows={weakest_frameworks} empty="No framework coverage yet." />
        </div>

        <div style={cardStyle}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Strongest Frameworks</div>
          <FrameworkCoverageList rows={strongest_frameworks} empty="No framework coverage yet." />
        </div>
      </div>

      {/* Trend */}
      <div style={cardStyle}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>30-Day Posture Trend</div>
        {coverage_trend.length === 0 ? (
          <div style={{ fontSize: 13, color: 'var(--color-text-muted)', textAlign: 'center', padding: 40 }}>
            No historical runs yet — trends appear after the second completed assessment.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={coverage_trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="var(--color-text-muted)" />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} stroke="var(--color-text-muted)" />
              <Tooltip contentStyle={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="security_score" name="Security" stroke="#1776D2" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="compliance_score" name="Compliance" stroke="#10B981" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="risk_score" name="Risk" stroke="#F59E0B" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Control state footer — each count opens the findings it stands for */}
      <div style={{ ...cardStyle, display: 'flex', gap: 24, flexWrap: 'wrap', fontSize: 13 }}>
        {[
          { label: 'Implemented', value: state_totals.implemented, color: '#10B981', state: 'implemented' },
          { label: 'Partially implemented', value: state_totals.partially_implemented, color: '#F59E0B', state: 'partially_implemented' },
          { label: 'Not implemented', value: state_totals.not_implemented, color: '#EF4444', state: 'not_implemented' },
          { label: 'Not applicable', value: state_totals.not_applicable, color: 'var(--color-info)', state: 'not_applicable' },
        ].map((s) => (
          <Link key={s.label} to={`/findings?state=${s.state}`} style={{ color: 'inherit', textDecoration: 'none' }}>
            <span style={{ fontSize: 18, fontWeight: 700, color: s.color }}>{s.value}</span>
            <span style={{ marginLeft: 6, color: 'var(--color-text-muted)' }}>{s.label}</span>
          </Link>
        ))}
      </div>
    </div>
  )
}
