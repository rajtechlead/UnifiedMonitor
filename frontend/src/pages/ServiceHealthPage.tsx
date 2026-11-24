import { useQuery } from '@tanstack/react-query'
import { Activity, AlertTriangle } from 'lucide-react'
import { errorDetail, monitoringApi } from '../hooks/useApi'

type Service = { service: string; status: string; open_issues?: number; link?: string }
type Issue = {
  id: string
  title: string
  severity: string
  status: string
  classification: string | null
  service: string | null
  feature: string | null
  feature_group: string | null
  origin: string | null
  start_time: string | null
  end_time: string | null
  last_modified_time: string | null
  is_resolved: boolean
  details: string | null
  latest_update: string | null
  link?: string
}
type Health = {
  services: Service[]
  active_issues: Issue[]
  degraded_services: number
  operational_services?: number
  services_with_advisories?: number
  advisories_by_severity?: Record<string, number>
  portal_url?: string
  generated_at: string
}

const portalLink = (value?: string) => value || 'https://admin.microsoft.com/#/servicehealth'

const statusColour = (status: string) => {
  const value = status.toLowerCase()
  if (value.includes('operational') || value === 'serviceoperational') return '#10B981'
  if (value.includes('restor') || value.includes('investigat')) return '#F59E0B'
  return '#EF4444'
}

export default function ServiceHealthPage() {
  const { data, isLoading, isError, error } = useQuery<Health>({
    queryKey: ['monitoring', 'service-health'],
    queryFn: monitoringApi.serviceHealth,
  })

  if (isLoading) {
    return <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>Reading service health from Microsoft Graph…</div>
  }
  if (isError || !data) {
    return (
      <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
        Service health is unavailable. The Microsoft app needs <code>ServiceHealth.Read.All</code> and admin consent.
        <div style={{ fontSize: 11, marginTop: 6 }}>
          {errorDetail(error, (error as Error)?.message || 'The request failed.')}
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Activity size={18} /> Service Health
        </h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          {data.services.length} services monitored · {data.operational_services ?? data.services.length - data.degraded_services} operational ·{' '}
          {data.degraded_services} degraded · {data.active_issues.length} open advisories
          {data.services_with_advisories ? ` across ${data.services_with_advisories} services` : ''}
          {' · '}
          <a href={portalLink(data.portal_url)} target="_blank" rel="noreferrer" style={{ color: 'var(--color-brand)' }}>
            Open Microsoft 365 service health
          </a>
        </p>
      </div>

      {data.advisories_by_severity && Object.keys(data.advisories_by_severity).length > 0 && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', fontSize: 12 }}>
          {Object.entries(data.advisories_by_severity).map(([severity, count]) => (
            <span key={severity} style={{
              padding: '4px 10px', borderRadius: 999, border: '1px solid var(--color-border)',
              background: 'var(--color-surface)', textTransform: 'capitalize',
            }}>
              {severity}: {count}
            </span>
          ))}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 12 }}>
        {data.services.map((service) => (
          <a
            key={service.service}
            href={portalLink(service.link ?? data.portal_url)}
            target="_blank"
            rel="noreferrer"
            title={`Open ${service.service} service health`}
            style={{
              background: 'var(--color-surface)', border: '1px solid var(--color-border)',
              borderRadius: 10, padding: 14, display: 'flex', alignItems: 'center', gap: 10,
              color: 'inherit', textDecoration: 'none',
            }}
          >
            <span style={{ width: 9, height: 9, borderRadius: '50%', background: statusColour(service.status) }} />
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, textTransform: 'capitalize' }}>{service.service}</div>
              <div style={{ fontSize: 11, color: statusColour(service.status) }}>
                {service.status}
                {service.open_issues ? ` · ${service.open_issues} open` : ''}
              </div>
            </div>
          </a>
        ))}
        {data.services.length === 0 && (
          <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>No service health data was returned.</div>
        )}
      </div>

      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, padding: 18,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertTriangle size={15} color="#F59E0B" /> Open advisories
        </div>
        {data.active_issues.length === 0 ? (
          <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>No unresolved advisories.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {data.active_issues.map((issue) => (
              <div key={issue.id} style={{
                border: '1px solid var(--color-border)', borderRadius: 8, padding: 12,
                display: 'flex', flexDirection: 'column', gap: 4,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                  <a href={portalLink(issue.link ?? data.portal_url)} target="_blank" rel="noreferrer" style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-brand)' }}>
                    {issue.title}
                  </a>
                  <span style={{ fontSize: 11, color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
                    {issue.service || '—'} · {issue.severity}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
                  {issue.id ? `${issue.id} · ` : ''}
                  {issue.status}
                  {issue.start_time ? ` · started ${new Date(issue.start_time).toLocaleString()}` : ''}
                  {issue.last_modified_time ? ` · updated ${new Date(issue.last_modified_time).toLocaleString()}` : ''}
                  {issue.classification ? ` · ${issue.classification}` : ''}
                  {issue.feature_group || issue.feature ? ` · ${[issue.feature_group, issue.feature].filter(Boolean).join(' / ')}` : ''}
                </div>
                {issue.details && (
                  <div style={{ fontSize: 12, color: 'var(--color-text)', marginTop: 4 }}>{issue.details}</div>
                )}
                {issue.latest_update && (
                  <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 4 }}>
                    Latest update: {issue.latest_update}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
