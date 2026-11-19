import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Search } from 'lucide-react'
import { searchApi } from '../hooks/useApi'

type Hit = {
  kind: string
  id: string
  title: string
  subtitle: string | null
  href: string
  severity: string | null
}

const PAGES: Hit[] = [
  ['Executive', '/executive'], ['CISO', '/ciso'], ['Clouds', '/clouds'], ['Zero Trust', '/zero-trust'],
  ['Zero Trust Assessment', '/zero-trust/assessment'],
  ['Security', '/security'], ['Compliance', '/compliance'], ['Risk', '/risk'], ['SOC', '/soc'],
  ['Audit', '/audit'], ['Findings', '/findings'], ['Alerts', '/alerts'], ['Assessments', '/assessments'],
  ['Reports', '/reports'], ['Licences', '/licenses'], ['Service Health', '/service-health'],
  ['Data Collection', '/collection'], ['Settings', '/settings'],
].map(([title, href]) => ({ kind: 'page', id: href, title, subtitle: null, href, severity: null }))

export default function SearchPalette({ open, onClose }: { readonly open: boolean; readonly onClose: () => void }) {
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query.trim()), 250)
    return () => clearTimeout(timer)
  }, [query])

  useEffect(() => {
    if (open) inputRef.current?.focus()
    else setQuery('')
  }, [open])

  const { data } = useQuery<{ hits: Hit[] }>({
    queryKey: ['search', debounced],
    queryFn: () => searchApi.search(debounced),
    enabled: open && debounced.length >= 2,
  })

  if (!open) return null

  const pageHits = PAGES.filter((page) => page.title.toLowerCase().includes(query.toLowerCase()))
  const apiHits = debounced.length >= 2 ? data?.hits ?? [] : []
  const groups: [string, Hit[]][] = [
    ['Pages', query ? pageHits : PAGES.slice(0, 6)],
    ['Findings & alerts', apiHits.filter((hit) => hit.kind !== 'control')],
    ['Controls', apiHits.filter((hit) => hit.kind === 'control')],
  ]

  const go = (href: string) => {
    onClose()
    navigate(href)
  }

  return (
    <div
      role="presentation"
      onClick={onClose}
      onKeyDown={(event) => { if (event.key === 'Escape') onClose() }}
      style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.45)',
        display: 'flex', alignItems: 'flex-start', justifyContent: 'center', paddingTop: '12vh', zIndex: 100 }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Search"
        onClick={(event) => event.stopPropagation()}
        style={{ width: '100%', maxWidth: 560, background: 'var(--color-surface)',
          border: '1px solid var(--color-border)', borderRadius: 12, overflow: 'hidden',
          boxShadow: 'var(--shadow-md)' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 14px',
          borderBottom: '1px solid var(--color-border)' }}>
          <Search size={16} color="var(--color-text-muted)" />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => { if (event.key === 'Escape') onClose() }}
            placeholder="Search pages, findings, alerts, controls…"
            style={{ flex: 1, border: 'none', outline: 'none', background: 'transparent',
              color: 'var(--color-text)', fontSize: 14 }}
          />
          <span style={{ fontSize: 10, color: 'var(--color-text-muted)' }}>Esc</span>
        </div>
        <div style={{ maxHeight: 360, overflowY: 'auto', padding: 6 }}>
          {groups.map(([label, hits]) => hits.length > 0 && (
            <div key={label}>
              <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '.06em',
                color: 'var(--color-text-muted)', padding: '8px 10px 4px' }}>{label}</div>
              {hits.map((hit) => (
                <button
                  key={`${hit.kind}-${hit.id}`}
                  onClick={() => go(hit.href)}
                  style={{ width: '100%', textAlign: 'left', display: 'flex', gap: 10,
                    justifyContent: 'space-between', padding: '8px 10px', borderRadius: 6,
                    border: 'none', background: 'transparent', color: 'var(--color-text)', cursor: 'pointer' }}
                >
                  <span style={{ fontSize: 13 }}>{hit.title}</span>
                  <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{hit.subtitle || hit.kind}</span>
                </button>
              ))}
            </div>
          ))}
          {query.length >= 2 && apiHits.length === 0 && (
            <div style={{ padding: 16, fontSize: 12, color: 'var(--color-text-muted)' }}>No matches.</div>
          )}
        </div>
      </div>
    </div>
  )
}
