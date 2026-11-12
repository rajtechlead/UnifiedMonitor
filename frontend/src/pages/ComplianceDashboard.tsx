import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '../hooks/useApi'
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, Tooltip } from 'recharts'

const FRAMEWORK_LABELS: Record<string, string> = {
  iso_27001_2022: 'ISO 27001:2022',
  iso_42001: 'ISO 42001',
  nist_csf_2: 'NIST CSF 2.0',
  nist_800_53: 'NIST 800-53 R5',
  cis_controls_v8: 'CIS Controls v8',
  cis_m365: 'CIS M365',
  zero_trust: 'Zero Trust',
  soc2: 'SOC 2',
  pci_dss_4: 'PCI-DSS 4.0',
  hipaa: 'HIPAA',
  gdpr: 'GDPR',
  cmmc_2: 'CMMC 2.0',
  cpcsc: 'CPCSC',
}

type FrameworkScore = {
  framework: string
  total: number
  implemented: number
  partial: number
  not_implemented: number
  not_applicable: number
  score: number
}

function FrameworkBar({ fw }: { fw: FrameworkScore }) {
  const impl = fw.implemented || 0
  const partial = fw.partial || 0
  const notImpl = fw.not_implemented || 0
  const na = fw.not_applicable || 0
  const total = impl + partial + notImpl + na || 1

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 500 }}>
          {FRAMEWORK_LABELS[fw.framework] || fw.framework}
        </span>
        <span style={{ fontSize: 13, fontWeight: 700, color: fw.score >= 80 ? '#10B981' : fw.score >= 60 ? '#F59E0B' : '#EF4444' }}>
          {fw.score}%
        </span>
      </div>
      <div style={{ height: 8, background: 'var(--color-surface-2)', borderRadius: 4, overflow: 'hidden', display: 'flex' }}>
        <div style={{ width: `${(impl / total) * 100}%`, background: '#10B981', transition: 'width 0.5s' }} />
        <div style={{ width: `${(partial / total) * 100}%`, background: '#F59E0B', transition: 'width 0.5s' }} />
        <div style={{ width: `${(notImpl / total) * 100}%`, background: '#EF4444', transition: 'width 0.5s' }} />
        <div style={{ width: `${(na / total) * 100}%`, background: 'var(--color-border)', transition: 'width 0.5s' }} />
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 4, fontSize: 11, color: 'var(--color-text-muted)' }}>
        <span style={{ color: '#10B981' }}>✓ {impl} implemented</span>
        <span style={{ color: '#F59E0B' }}>~ {partial} partial</span>
        <span style={{ color: '#EF4444' }}>✗ {notImpl} not implemented</span>
        {na > 0 && <span>N/A {na}</span>}
      </div>
    </div>
  )
}

export default function ComplianceDashboard() {
  const { data: compliance, isLoading } = useQuery({
    queryKey: ['dashboard', 'compliance'],
    queryFn: dashboardApi.getCompliance,
  })

  const frameworks: FrameworkScore[] = compliance?.frameworks || []

  // Build radar data from top frameworks
  const radarData = frameworks.slice(0, 8).map(fw => ({
    subject: (FRAMEWORK_LABELS[fw.framework] || fw.framework).replace(' ', '\n'),
    score: fw.score,
  }))

  const avgScore = frameworks.length
    ? Math.round(frameworks.reduce((s, f) => s + f.score, 0) / frameworks.length)
    : 0

  const fullyCompliant = frameworks.filter(f => f.score >= 90).length
  const atRisk = frameworks.filter(f => f.score < 50).length

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
          { label: 'Avg Compliance Score', value: `${avgScore}%`, color: avgScore >= 70 ? '#10B981' : '#F59E0B' },
          { label: 'Fully Compliant (≥90%)', value: fullyCompliant, color: '#10B981' },
          { label: 'Active Frameworks', value: frameworks.length, color: 'var(--color-brand)' },
          { label: 'At Risk (<50%)', value: atRisk, color: '#EF4444' },
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

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: 16 }}>
        {/* Radar chart */}
        <div style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 12, padding: 20,
        }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Compliance Radar</div>
          {radarData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="var(--color-border)" />
                <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10 }} />
                <Radar dataKey="score" stroke="var(--color-brand)" fill="var(--color-brand)" fillOpacity={0.25} />
                <Tooltip contentStyle={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', fontSize: 12 }} />
              </RadarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ textAlign: 'center', padding: 60, color: 'var(--color-text-muted)', fontSize: 13 }}>
              Run an assessment to see radar data
            </div>
          )}
        </div>

        {/* Legend */}
        <div style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 12, padding: 20,
        }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Legend</div>
          <div style={{ display: 'flex', gap: 16, marginBottom: 20 }}>
            {[
              { color: '#10B981', label: 'Implemented' },
              { color: '#F59E0B', label: 'Partial' },
              { color: '#EF4444', label: 'Not Implemented' },
              { color: 'var(--color-border)', label: 'N/A' },
            ].map(l => (
              <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                <div style={{ width: 10, height: 10, borderRadius: 2, background: l.color, flexShrink: 0 }} />
                {l.label}
              </div>
            ))}
          </div>
          <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 16 }}>Score = Implemented / (Total − N/A) × 100</div>
        </div>
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
          frameworks.map((fw) => <FrameworkBar key={fw.framework} fw={fw} />)
        )}
      </div>
    </div>
  )
}
