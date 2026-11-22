import type { ReactNode } from 'react'

export interface StatCard {
  label: string
  value: ReactNode
  color: string
}

/** KPI row shared by the dashboards: one card per metric on the 160px grid. */
export default function StatCards({ cards }: Readonly<{ cards: StatCard[] }>) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16 }}>
      {cards.map(card => (
        <div key={card.label} style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 12, padding: 20, textAlign: 'center',
        }}>
          <div style={{ fontSize: 28, fontWeight: 700, color: card.color }}>{card.value}</div>
          <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 4 }}>{card.label}</div>
        </div>
      ))}
    </div>
  )
}
