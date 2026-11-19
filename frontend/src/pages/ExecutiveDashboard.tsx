import { useQuery } from '@tanstack/react-query'
import {
  RadialBarChart, RadialBar, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Tooltip, Cell, LineChart, Line, CartesianGrid,
} from 'recharts'
import { dashboardApi } from '../hooks/useApi'
import { TrendingUp, Shield, CheckCircle, AlertTriangle } from 'lucide-react'

type TrendPoint = { date: string; security_score: number; compliance_score: number; risk_score: number }
type FrameworkCoverage = {
  framework_id: string; framework_name: string
  coverage_pct: number; controls_total: number; controls_passed: number
}
type TopRisk = {
  id: string; title: string; severity: string
  category: string; service: string; first_detected_at: string
}
type ZeroTrustScore = {
  source: string; platform: string; has_run: boolean
  score: number; total: number; passed: number; failed: number; last_run: string | null
}

function scoreColour(score: number) {
  return score >= 80 ? '#10B981' : score >= 50 ? '#F59E0B' : '#EF4444'
}

function ScoreGauge({ label, score, color }: { label: string; score: number; color: string }) {
  const data = [{ value: score, fill: color }, { value: 100 - score, fill: 'var(--color-surface-2)' }]
  return (
    <div style={{
      background: 'var(--color-surface)',
      border: '1px solid var(--color-border)',
      borderRadius: 12,
      padding: 20,
      textAlign: 'center',
      minWidth: 160,
    }}>
      <ResponsiveContainer width="100%" height={120}>
        <RadialBarChart
          innerRadius="60%" outerRadius="90%"
          data={data} startAngle={180} endAngle={0}
        >
          <RadialBar dataKey="value" cornerRadius={6} />
        </RadialBarChart>
      </ResponsiveContainer>
      <div style={{ marginTop: -24 }}>
        <div style={{ fontSize: 28, fontWeight: 700, color }}>{Math.round(score)}</div>
        <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 2 }}>{label}</div>
      </div>
    </div>
  )
}

function StatCard({ icon: Icon, label, value, sub, color }: {
  icon: React.ElementType; label: string; value: string | number; sub?: string; color: string
}) {
  return (
    <div style={{
      background: 'var(--color-surface)', border: '1px solid var(--color-border)',
      borderRadius: 12, padding: 20, display: 'flex', alignItems: 'center', gap: 16,
    }}>
      <div style={{
        width: 48, height: 48, borderRadius: 12,
        background: `${color}20`, display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Icon size={22} color={color} />
      </div>
      <div>
        <div style={{ fontSize: 24, fontWeight: 700 }}>{value}</div>
        <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{label}</div>
        {sub && <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 2 }}>{sub}</div>}
      </div>
    </div>
  )
}

const tooltipStyle = {
  background: 'var(--color-surface-2)',
  border: '1px solid var(--color-border)',
  fontSize: 12,
}

export default function ExecutiveDashboard() {
  const { data: exec, isLoading } = useQuery({
    queryKey: ['dashboard', 'executive'],
    queryFn: dashboardApi.getExecutive,
  })

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300,
        color: 'var(--color-text-muted)' }}>
        Loading dashboard…
      </div>
    )
  }

  const scores = exec?.scores ?? { security_score: 0, compliance_score: 0, risk_score: 0 }
  const trends: TrendPoint[] = exec?.score_trends ?? []
  const frameworks: FrameworkCoverage[] = exec?.framework_coverage ?? []
  const topRisks: TopRisk[] = exec?.top_risks ?? []
  const ztPlatforms = (exec?.zero_trust ?? []) as ZeroTrustScore[]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Executive Dashboard</h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          Unified security and compliance overview
        </p>
      </div>

      {/* Score gauges */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <ScoreGauge label="Security Score" score={scores.security_score} color="var(--color-brand)" />
        <ScoreGauge label="Compliance Score" score={scores.compliance_score} color="#10B981" />
        <ScoreGauge label="Risk Score" score={scores.risk_score} color="#F59E0B" />
      </div>

      {/* Zero Trust Assessment — latest imported score per platform */}
      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, padding: 20,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Zero Trust Assessment</div>
        <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 16 }}>
          Latest score per platform
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
          {ztPlatforms.map((p) => (
            <div key={p.source} style={{ border: '1px solid var(--color-border)', borderRadius: 10, padding: 14 }}>
              <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{p.platform}</div>
              <div style={{
                fontSize: 22, fontWeight: 700,
                color: p.has_run ? scoreColour(p.score) : 'var(--color-text-muted)',
              }}>
                {p.has_run ? Math.round(p.score) : '—'}
              </div>
              <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
                {p.has_run
                  ? `${p.passed}/${p.total} passing${p.last_run ? ` · ${new Date(p.last_run).toLocaleDateString()}` : ''}`
                  : 'Not assessed'}
              </div>
            </div>
          ))}
          {ztPlatforms.length === 0 && (
            <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
              No Zero Trust assessment yet. Import a report from the ZT Assessment page.
            </div>
          )}
        </div>
      </div>

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
        <StatCard icon={Shield} label="Asset Coverage" value={`${Math.round(exec?.asset_coverage_pct ?? 0)}%`}
          sub="Monitored assets" color="var(--color-brand)" />
        <StatCard icon={CheckCircle} label="Remediation Progress" value={`${Math.round(exec?.remediation_progress_pct ?? 0)}%`}
          sub="Controls remediated" color="#10B981" />
        <StatCard icon={TrendingUp} label="Frameworks Monitored" value={frameworks.length}
          sub="Active GRC frameworks" color="#3B82F6" />
        <StatCard icon={AlertTriangle} label="Top Risks" value={topRisks.length}
          sub="Ranked by severity" color="#EF4444" />
      </div>

      {/* Charts row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Framework coverage */}
        <div style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 12, padding: 20,
        }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Framework Coverage</div>
          {frameworks.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 60, color: 'var(--color-text-muted)', fontSize: 13 }}>
              No framework data yet. Run an assessment.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={frameworks.slice(0, 8)} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
                <XAxis dataKey="framework_id" tick={{ fontSize: 10 }} interval={0} angle={-30} textAnchor="end" height={60} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar dataKey="coverage_pct" name="Coverage %" radius={[4, 4, 0, 0]}>
                  {frameworks.slice(0, 8).map((fw) => (
                    <Cell key={fw.framework_id} fill={fw.coverage_pct >= 80 ? '#10B981' : fw.coverage_pct >= 50 ? '#F59E0B' : '#EF4444'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Score trend */}
        <div style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 12, padding: 20,
        }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Score Trend (30d)</div>
          {trends.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 60, color: 'var(--color-text-muted)', fontSize: 13 }}>
              No historical scores yet. Run assessments to build a trend.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={trends} margin={{ top: 0, right: 8, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line type="monotone" dataKey="security_score" name="Security" stroke="var(--color-brand)" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="compliance_score" name="Compliance" stroke="#10B981" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="risk_score" name="Risk" stroke="#F59E0B" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Top risks table */}
      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, padding: 20,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Top Risks</div>
        {topRisks.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 32, color: 'var(--color-text-muted)', fontSize: 13 }}>
            No open risks. Run an assessment to populate.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                {['Title', 'Severity', 'Category', 'Service', 'First Detected'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '8px 12px', fontWeight: 600,
                    color: 'var(--color-text-muted)', fontSize: 12 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {topRisks.map((f) => (
                <tr key={f.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '10px 12px' }}>{f.title}</td>
                  <td style={{ padding: '10px 12px' }}>
                    <span className={`severity-chip severity-${f.severity?.toLowerCase()}`}>{f.severity}</span>
                  </td>
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
