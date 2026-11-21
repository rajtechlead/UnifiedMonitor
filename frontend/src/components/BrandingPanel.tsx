import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Palette, Save } from 'lucide-react'
import { api, errorDetail } from '../hooks/useApi'

type Branding = {
  portal_name: string
  accent_colour: string
  logo_url: string | null
  support_email: string | null
}

const FIELD_STYLE: React.CSSProperties = {
  width: '100%', padding: '9px 12px', fontSize: 13, border: '1px solid var(--color-border)',
  borderRadius: 7, background: 'var(--color-surface-2)', color: 'var(--color-text)', outline: 'none',
}

const LABEL_STYLE: React.CSSProperties = {
  display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 6,
}

export default function BrandingPanel() {
  const [form, setForm] = useState<Branding>({ portal_name: 'UniMonitor', accent_colour: '#2563EB', logo_url: '', support_email: '' })
  const [message, setMessage] = useState('')

  const { data } = useQuery<Branding>({
    queryKey: ['branding'],
    queryFn: () => api.get('/settings/branding').then((response) => response.data),
  })

  useEffect(() => {
    if (data) setForm({ ...data, logo_url: data.logo_url ?? '', support_email: data.support_email ?? '' })
  }, [data])

  const save = useMutation({
    mutationFn: () => api.put('/settings/branding', {
      portal_name: form.portal_name,
      accent_colour: form.accent_colour,
      logo_url: form.logo_url || null,
      support_email: form.support_email || null,
    }),
    onSuccess: () => {
      setMessage('Branding saved. Reload to apply it everywhere.')
      document.documentElement.style.setProperty('--color-brand', form.accent_colour)
    },
    onError: (error: unknown) => {
      setMessage(errorDetail(error, 'Could not save branding.'))
    },
  })

  return (
    <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 12, padding: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
        <Palette size={18} color="var(--color-brand)" />
        <span style={{ fontSize: 15, fontWeight: 600 }}>Portal branding</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14 }}>
        <div>
          <label style={LABEL_STYLE} htmlFor="branding-name">Portal name</label>
          <input id="branding-name" value={form.portal_name} maxLength={64}
            onChange={(event) => setForm({ ...form, portal_name: event.target.value })} style={FIELD_STYLE} />
        </div>
        <div>
          <label style={LABEL_STYLE} htmlFor="branding-colour">Accent colour</label>
          <input id="branding-colour" value={form.accent_colour} pattern="^#[0-9A-Fa-f]{6}$"
            onChange={(event) => setForm({ ...form, accent_colour: event.target.value })} style={FIELD_STYLE} />
        </div>
        <div>
          <label style={LABEL_STYLE} htmlFor="branding-logo">Logo URL (https or /path)</label>
          <input id="branding-logo" value={form.logo_url ?? ''} maxLength={512}
            onChange={(event) => setForm({ ...form, logo_url: event.target.value })} style={FIELD_STYLE} />
        </div>
        <div>
          <label style={LABEL_STYLE} htmlFor="branding-email">Support email</label>
          <input id="branding-email" value={form.support_email ?? ''} maxLength={254}
            onChange={(event) => setForm({ ...form, support_email: event.target.value })} style={FIELD_STYLE} />
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 16 }}>
        <button
          onClick={() => save.mutate()}
          disabled={save.isPending}
          style={{
            padding: '8px 16px', fontSize: 13, background: 'var(--color-brand)', color: 'white',
            border: 'none', borderRadius: 8, cursor: save.isPending ? 'wait' : 'pointer',
            display: 'flex', alignItems: 'center', gap: 6,
          }}
        >
          <Save size={14} /> {save.isPending ? 'Saving…' : 'Save branding'}
        </button>
        {message && <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{message}</span>}
      </div>
    </div>
  )
}
