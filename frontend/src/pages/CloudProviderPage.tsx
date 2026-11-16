import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { dashboardApi } from '../hooks/useApi'

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
  finding_counts: { critical: number; high: number; medium: number; low: number; informational: number; total: number }
  state_counts: { implemented: number; partially_implemented: number; not_implemented: number; not_applicable: number }
  services: string[]
  collectors: string[]
  credential_settings: string[]
}

type ServiceRow = { service: string; controls_total: number; controls_passed: number; findings: number }
type CategoryRow = { category: string; controls_total: number; controls_passed: number; coverage_pct: number }
type FrameworkRow = { framework_id: string; framework_name: string; coverage_pct: number; controls_total: number; controls_passed: number }
type FindingRow = { id: string; title: string; severity: string; category: string; service: string; first_detected_at: string }

type ProviderDetail = {
  provider: ProviderSummary
  services: ServiceRow[]
  categories: CategoryRow[]
  frameworks: FrameworkRow[]
  top_findings: FindingRow[]
}

const scoreColor = (pct: number) => (pct >= 80 ? '#10B981' : pct >= 60 ? '#F59E0B' : '#EF4444')

const cardStyle = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  borderRadius: 12,
  padding: 20,
}

function CoverageBar({ label, passed, total, pct }: { label: string; passed: number; total: number; pct: number }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 500 }}>{label}</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: scoreColor(pct) }}>{Math.round(pct)}%</span>
      </div>
      <div style={{ height: 8, background: 'var(--color-surface-2)', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ width: `${Math.min(100, pct)}%`, height: '100%', background: scoreColor(pct) }} />
      </div>
      <div style={{ marginTop: 4, fontSize: 11, color: 'var(--color-text-muted)' }}>
        {passed} / {total} controls passing
      </div>
    </div>
  )
}

export default function CloudProviderPage() {
  const { providerId = '' } = useParams()
  const { data, isLoading, isError, error } = useQuery<ProviderDetail>({
    queryKey: ['dashboard', 'clouds', providerId],
    queryFn: () => dashboardApi.getCloudProvider(providerId),
    enabled: Boolean(providerId),
  })

  if (isLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300,
        color: 'var(--color-text-muted)' }}>
        Loading cloud provider…
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div style={{ ...cardStyle, textAlign: 'center', color: 'var(--color-text-muted)' }}>
        <div style={{ marginBottom: 8 }}>
          {(error as { response?: { status?: number } })?.response?.status === 404
            ? `Unknown cloud provider "${providerId}".`
            : 'Could not load this cloud provider.'}
        </div>
        <Link to="/clouds">← Back to multi-cloud</Link>
      </div>
    )
  }

  const { provider, services, categories, frameworks, top_findings } = data

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <Link to="/clouds" style={{ fontSize: 12 }}>← Multi-cloud</Link>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginTop: 6 }}>{provider.name}</h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>{provider.description}</p>
      </div>

      {!provider.connected && (
        <div style={{ ...cardStyle, borderColor: 'var(--color-high)', background: 'var(--color-high-bg)', color: 'var(--color-text)' }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>No data collected yet</div>
          <div style={{ fontSize: 12 }}>
            Configure {provider.credential_settings.join(', ')} and run the{' '}
            {provider.collectors.join(', ')} collector to populate this dashboard. Until then, controls report
            <em> not implemented</em> rather than passing.
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 16 }}>
        {[
          { label: 'Security Score', value: Math.round(provider.scores.security_score), color: scoreColor(provider.scores.security_score) },
          { label: 'Compliance Score', value: Math.round(provider.scores.compliance_score), color: scoreColor(provider.scores.compliance_score) },
          { label: 'Risk Score', value: Math.round(provider.scores.risk_score), color: scoreColor(provider.scores.risk_score) },
          { label: 'Controls Passing', value: `${provider.controls_passed}/${provider.controls_total}`, color: 'var(--color-brand)' },
          { label: 'Critical', value: provider.finding_counts.critical, color: '#EF4444' },
          { label: 'High', value: provider.finding_counts.high, color: '#F59E0B' },
        ].map((card) => (
          <div key={card.label} style={{ ...cardStyle, textAlign: 'center' }}>
            <div style={{ fontSize: 26, fontWeight: 700, color: card.color }}>{card.value}</div>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 4 }}>{card.label}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        {/* Control state mix */}
        <div style={cardStyle}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Control States</div>
          {[
            { label: 'Implemented', value: provider.state_counts.implemented, color: 'var(--color-pass)' },
            { label: 'Partial', value: provider.state_counts.partially_implemented, color: 'var(--color-medium)' },
            { label: 'Not implemented', value: provider.state_counts.not_implemented, color: 'var(--color-critical)' },
            { label: 'Not applicable', value: provider.state_counts.not_applicable, color: 'var(--color-info)' },
          ].map((row) => (
            <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', fontSize: 13 }}>
              <span style={{ color: 'var(--color-text-secondary)' }}>{row.label}</span>
              <span style={{ fontWeight: 700, color: row.color }}>{row.value}</span>
            </div>
          ))}
        </div>

        {/* Services */}
        <div style={cardStyle}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Services</div>
          {services.map((s) => (
            <div key={s.service} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', fontSize: 13 }}>
              <span style={{ color: 'var(--color-text-secondary)', fontFamily: 'monospace' }}>{s.service}</span>
              <span>
                <span style={{ color: 'var(--color-text-muted)' }}>{s.controls_passed}/{s.controls_total} · </span>
                <span style={{ fontWeight: 600 }}>{s.findings} findings</span>
              </span>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        <div style={cardStyle}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Coverage by Category</div>
          {categories.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>No controls registered for this provider.</div>
          ) : (
            categories.map((c) => (
              <CoverageBar key={c.category} label={c.category} passed={c.controls_passed} total={c.controls_total} pct={c.coverage_pct} />
            ))
          )}
        </div>

        <div style={cardStyle}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Framework Coverage</div>
          {frameworks.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
              Run an assessment to map this provider's controls to compliance frameworks.
            </div>
          ) : (
            frameworks.map((fw) => (
              <CoverageBar key={fw.framework_id} label={fw.framework_name} passed={fw.controls_passed} total={fw.controls_total} pct={fw.coverage_pct} />
            ))
          )}
        </div>
      </div>

      {/* Top findings */}
      <div style={cardStyle}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Top Open Findings</div>
        {top_findings.length === 0 ? (
          <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
            No open findings for this provider.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--color-text-muted)', fontSize: 11, textTransform: 'uppercase' }}>
                <th style={{ padding: '6px 8px' }}>Severity</th>
                <th style={{ padding: '6px 8px' }}>Title</th>
                <th style={{ padding: '6px 8px' }}>Category</th>
                <th style={{ padding: '6px 8px' }}>Service</th>
              </tr>
            </thead>
            <tbody>
              {top_findings.map((f) => (
                <tr key={f.id} style={{ borderTop: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '8px' }}>
                    <span className={`severity-chip severity-${f.severity === 'informational' ? 'info' : f.severity}`}>
                      {f.severity}
                    </span>
                  </td>
                  <td style={{ padding: '8px', fontWeight: 500 }}>{f.title}</td>
                  <td style={{ padding: '8px', color: 'var(--color-text-secondary)' }}>{f.category}</td>
                  <td style={{ padding: '8px', color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>{f.service}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
