import { useQuery } from '@tanstack/react-query'
import { Activity, AlertTriangle } from 'lucide-react'
import { errorDetail, monitoringApi } from '../hooks/useApi'

type Service = { service: string; status: string }
type Issue = {
  id: string
  title: string
  severity: string
  status: string
  classification: string | null
  service: string | null
  start_time: string | null
  end_time: string | null
  is_resolved: boolean
  details: string | null
}
type Health = {
  services: Service[]
  active_issues: Issue[]
  degraded_services: number
  generated_at: string
}

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
          {data.services.length} services · {data.degraded_services} not operational · {data.active_issues.length} open advisories
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 12 }}>
        {data.services.map((service) => (
          <div key={service.service} style={{
            background: 'var(--color-surface)', border: '1px solid var(--color-border)',
            borderRadius: 10, padding: 14, display: 'flex', alignItems: 'center', gap: 10,
          }}>
            <span style={{ width: 9, height: 9, borderRadius: '50%', background: statusColour(service.status) }} />
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, textTransform: 'capitalize' }}>{service.service}</div>
              <div style={{ fontSize: 11, color: statusColour(service.status) }}>{service.status}</div>
            </div>
          </div>
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
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{issue.title}</span>
                  <span style={{ fontSize: 11, color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
                    {issue.service || '—'} · {issue.severity}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
                  {issue.status}
                  {issue.start_time ? ` · started ${new Date(issue.start_time).toLocaleString()}` : ''}
                  {issue.classification ? ` · ${issue.classification}` : ''}
                </div>
                {issue.details && (
                  <div style={{ fontSize: 12, color: 'var(--color-text)', marginTop: 4 }}>{issue.details}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
