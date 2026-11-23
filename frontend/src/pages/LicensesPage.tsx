import { useQuery } from '@tanstack/react-query'
import TableHead from '../components/TableHead'
import { KeyRound } from 'lucide-react'
import { errorDetail, monitoringApi } from '../hooks/useApi'

type Sku = {
  sku_id: string
  sku_part_number: string
  capability_status: string
  consumed: number
  prepaid: number
  available: number
  utilisation_pct: number
  status: 'healthy' | 'unused' | 'over' | 'suspended'
}

type Licensing = {
  skus: Sku[]
  total_seats: number
  consumed_seats: number
  available_seats: number
  utilisation_pct: number
  unused_skus: number
  generated_at: string
}

const statusColour: Record<string, string> = {
  healthy: '#10B981',
  unused: '#F59E0B',
  over: '#EF4444',
  suspended: '#64748B',
}

export default function LicensesPage() {
  const { data, isLoading, isError, error } = useQuery<Licensing>({
    queryKey: ['monitoring', 'licensing'],
    queryFn: monitoringApi.licensing,
  })

  if (isLoading) {
    return <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>Reading licence data from Microsoft Graph…</div>
  }
  if (isError || !data) {
    return (
      <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
        Licence posture is unavailable. Check the Microsoft connection and that the app can read{' '}
        <code>Organization.Read.All</code>.
        <div style={{ fontSize: 11, marginTop: 6 }}>
          {errorDetail(error, (error as Error)?.message || 'The request failed.')}
        </div>
      </div>
    )
  }

  const cards = [
    { label: 'Seats purchased', value: data.total_seats, colour: 'var(--color-brand)' },
    { label: 'Seats assigned', value: data.consumed_seats, colour: '#10B981' },
    { label: 'Seats available', value: data.available_seats, colour: '#F59E0B' },
    { label: 'Utilisation', value: `${data.utilisation_pct}%`, colour: '#8B5CF6' },
    { label: 'Fully unused SKUs', value: data.unused_skus, colour: '#EF4444' },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4, display: 'flex', alignItems: 'center', gap: 8 }}>
          <KeyRound size={18} /> Licence Posture
        </h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          What you pay for, what is assigned, and what is sitting idle · updated {new Date(data.generated_at).toLocaleString()}
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 14 }}>
        {cards.map((item) => (
          <div key={item.label} style={{
            background: 'var(--color-surface)', border: '1px solid var(--color-border)',
            borderRadius: 12, padding: 18, textAlign: 'center',
          }}>
            <div style={{ fontSize: 26, fontWeight: 700, color: item.colour }}>{item.value}</div>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 4 }}>{item.label}</div>
          </div>
        ))}
      </div>

      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, overflow: 'hidden',
      }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <TableHead headers={['SKU', 'Status', 'Assigned', 'Purchased', 'Available', 'Utilisation']} />
          <tbody>
            {data.skus.map((sku) => (
              <tr key={sku.sku_id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                <td style={{ padding: '10px 14px', fontWeight: 600 }}>{sku.sku_part_number}</td>
                <td style={{ padding: '10px 14px' }}>
                  <span style={{
                    fontSize: 11, padding: '2px 8px', borderRadius: 999, textTransform: 'capitalize',
                    background: `${statusColour[sku.status]}1A`, color: statusColour[sku.status],
                  }}>
                    {sku.status}
                  </span>
                </td>
                <td style={{ padding: '10px 14px' }}>{sku.consumed}</td>
                <td style={{ padding: '10px 14px' }}>{sku.prepaid}</td>
                <td style={{ padding: '10px 14px' }}>{sku.available}</td>
                <td style={{ padding: '10px 14px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ flex: 1, height: 6, borderRadius: 3, background: 'var(--color-surface-2)', maxWidth: 120 }}>
                      <div style={{ height: 6, borderRadius: 3, width: `${Math.min(100, sku.utilisation_pct)}%`,
                        background: statusColour[sku.status] }} />
                    </div>
                    <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{sku.utilisation_pct}%</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data.skus.length === 0 && (
          <div style={{ padding: 32, textAlign: 'center', fontSize: 13, color: 'var(--color-text-muted)' }}>
            No licence SKUs were returned for this tenant.
          </div>
        )}
      </div>
    </div>
  )
}
