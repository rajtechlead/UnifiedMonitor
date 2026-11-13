import { useQuery } from '@tanstack/react-query'
import {
  RadialBarChart, RadialBar, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Tooltip, Cell, LineChart, Line, CartesianGrid,
} from 'recharts'
import { dashboardApi, findingsApi } from '../hooks/useApi'
import { AlertTriangle, CheckCircle, TrendingUp, Shield } from 'lucide-react'

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: '#EF4444',
  HIGH: '#F59E0B',
  MEDIUM: '#3B82F6',
  LOW: '#10B981',
  INFORMATIONAL: '#6B7280',
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
        <div style={{ fontSize: 28, fontWeight: 700, color }}>{score}</div>
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

export default function ExecutiveDashboard() {
  const { data: exec, isLoading: execLoading } = useQuery({
    queryKey: ['dashboard', 'executive'],
    queryFn: dashboardApi.getExecutive,
  })
  const { data: findings, isLoading: findingsLoading } = useQuery({
    queryKey: ['findings', 'top'],
    queryFn: () => findingsApi.list({ limit: 10, severity: 'CRITICAL,HIGH', state: 'open' }),
  })

  if (execLoading || findingsLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300,
        color: 'var(--color-text-muted)' }}>
        Loading dashboard…
      </div>
    )
  }

  const scores = exec?.scores || { security: 72, compliance: 68, risk: 61 }
  const severityCounts = exec?.severity_counts || { CRITICAL: 4, HIGH: 12, MEDIUM: 23, LOW: 18, INFORMATIONAL: 5 }
  const trendData = exec?.trend || Array.from({ length: 7 }, (_, i) => ({
    date: `Day ${i + 1}`, score: 60 + Math.floor(Math.random() * 15),
  }))

  const severityBarData = Object.entries(severityCounts).map(([k, v]) => ({ name: k, count: v }))
  const topFindings: Array<Record<string, unknown>> = findings?.items || []

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
        <ScoreGauge label="Security Score" score={scores.security} color="var(--color-brand)" />
        <ScoreGauge label="Compliance Score" score={scores.compliance} color="#10B981" />
        <ScoreGauge label="Risk Score" score={scores.risk} color="#F59E0B" />
      </div>

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
        <StatCard icon={AlertTriangle} label="Critical Findings" value={severityCounts.CRITICAL || 0}
          sub="Requires immediate action" color="#EF4444" />
        <StatCard icon={Shield} label="Controls Assessed" value={exec?.controls_assessed || 0}
          sub={`of ${exec?.controls_total || 0} total`} color="var(--color-brand)" />
        <StatCard icon={CheckCircle} label="Frameworks Active" value={exec?.frameworks_active || 0}
          sub="GRC frameworks monitored" color="#10B981" />
        <StatCard icon={TrendingUp} label="Findings This Week" value={exec?.findings_this_week || 0}
          sub="New open findings" color="#F59E0B" />
      </div>

      {/* Charts row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Severity distribution */}
        <div style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 12, padding: 20,
        }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Findings by Severity</div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={severityBarData} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', fontSize: 12 }} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {severityBarData.map((entry) => (
                  <Cell key={entry.name} fill={SEVERITY_COLORS[entry.name] || '#6B7280'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Score trend */}
        <div style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 12, padding: 20,
        }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Security Score Trend</div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={trendData} margin={{ top: 0, right: 8, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', fontSize: 12 }} />
              <Line type="monotone" dataKey="score" stroke="var(--color-brand)" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Top findings table */}
      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, padding: 20,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Top Critical & High Findings</div>
        {topFindings.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 32, color: 'var(--color-text-muted)', fontSize: 13 }}>
            No critical or high findings. Great job!
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                {['Control', 'Title', 'Severity', 'Framework', 'State'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '8px 12px', fontWeight: 600,
                    color: 'var(--color-text-muted)', fontSize: 12 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {topFindings.map((f) => (
                <tr key={f.id as string} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '10px 12px', fontFamily: 'monospace', fontSize: 11 }}>
                    {f.control_id as string}
                  </td>
                  <td style={{ padding: '10px 12px' }}>{f.title as string}</td>
                  <td style={{ padding: '10px 12px' }}>
                    <span className={`severity-chip severity-${(f.severity as string)?.toLowerCase()}`}>
                      {f.severity as string}
                    </span>
                  </td>
                  <td style={{ padding: '10px 12px', color: 'var(--color-text-muted)' }}>
                    {f.framework as string}
                  </td>
                  <td style={{ padding: '10px 12px', textTransform: 'capitalize' }}>
                    {f.state as string}
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
