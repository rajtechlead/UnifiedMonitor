import { useQuery } from '@tanstack/react-query'
import { ShieldCheck, ShieldAlert, ShieldQuestion } from 'lucide-react'
import { dashboardApi } from '../hooks/useApi'

type Pillar = {
  id: string
  name: string
  description: string
  controls_total: number
  implemented: number
  partial: number
  not_implemented: number
  coverage_pct: number
  status: 'covered' | 'gap' | 'uncovered'
}

type ZeroTrustResponse = {
  pillars: Pillar[]
  overall_coverage_pct: number
}

const colourFor = (pct: number) => {
  if (pct >= 80) return '#10B981'
  if (pct >= 60) return '#F59E0B'
  return '#EF4444'
}

const statusCopy = {
  covered: { label: 'Covered', colour: '#10B981', Icon: ShieldCheck },
  gap: { label: 'Gap', colour: '#F59E0B', Icon: ShieldAlert },
  uncovered: { label: 'No controls', colour: '#94A3B8', Icon: ShieldQuestion },
}

export default function ZeroTrustPage() {
  const { data, isLoading, isError } = useQuery<ZeroTrustResponse>({
    queryKey: ['dashboard', 'zero-trust'],
    queryFn: dashboardApi.getZeroTrust,
  })

  if (isLoading) {
    return <div style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>Loading Zero Trust coverage…</div>
  }
  if (isError || !data) {
    return <div style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>Zero Trust coverage is unavailable.</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Zero Trust</h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          Coverage per pillar, grouped from each control's Zero Trust mapping.
          Overall covered-pillar score: <strong>{data.overall_coverage_pct}%</strong>
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
        {data.pillars.map((pillar) => {
          const status = statusCopy[pillar.status]
          return (
            <div key={pillar.id} style={{
              background: 'var(--color-surface)', border: '1px solid var(--color-border)',
              borderRadius: 12, padding: 18, display: 'flex', flexDirection: 'column', gap: 12,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <status.Icon size={18} color={status.colour} />
                  <span style={{ fontSize: 15, fontWeight: 600 }}>{pillar.name}</span>
                </div>
                <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999,
                  background: `${status.colour}1A`, color: status.colour }}>
                  {status.label}
                </span>
              </div>

              <p style={{ fontSize: 12, color: 'var(--color-text-muted)', margin: 0, lineHeight: 1.5 }}>
                {pillar.description}
              </p>

              <div>
                <div style={{ fontSize: 24, fontWeight: 700, color: colourFor(pillar.coverage_pct) }}>
                  {pillar.coverage_pct}%
                </div>
                <div style={{ height: 6, borderRadius: 3, background: 'var(--color-surface-2)', marginTop: 6 }}>
                  <div style={{ height: 6, borderRadius: 3, width: `${pillar.coverage_pct}%`,
                    background: colourFor(pillar.coverage_pct) }} />
                </div>
              </div>

              <div style={{ display: 'flex', gap: 14, fontSize: 11, color: 'var(--color-text-muted)' }}>
                <span>{pillar.controls_total} controls</span>
                <span>{pillar.implemented} implemented</span>
                <span>{pillar.not_implemented} failing</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
