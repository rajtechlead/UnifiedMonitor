import { Save } from 'lucide-react'

/**
 * The save row shared by the branding and client-settings forms: one button,
 * one "Saving…" state and one status message, so the two panels cannot drift.
 */
export default function SaveButton({ pending, label, message, onClick }: Readonly<{
  pending: boolean
  label: string
  message?: string
  onClick: () => void
}>) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <button
        type="button"
        onClick={onClick}
        disabled={pending}
        style={{
          padding: '8px 16px', fontSize: 13, background: 'var(--color-brand)', color: 'white',
          border: 'none', borderRadius: 8, cursor: pending ? 'wait' : 'pointer',
          display: 'flex', alignItems: 'center', gap: 6,
        }}
      >
        <Save size={14} /> {pending ? 'Saving…' : label}
      </button>
      {message && <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{message}</span>}
    </div>
  )
}
