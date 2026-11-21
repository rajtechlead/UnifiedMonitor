import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ArrowRight, CheckCircle2, CircleSlash, Search } from 'lucide-react'
import { zerotrustApi } from '../hooks/useApi'

type MappingControl = { id: string; title: string; service: string; pillar: string }
type MappingTest = {
  check_id: string
  title: string
  pillar: string
  category: string
  severity: string
  controls: MappingControl[]
}
type Mapping = {
  source: string
  platform: string
  catalogue: string
  tests: MappingTest[]
  total_tests: number
  mapped_tests: number
  unmapped_tests: number
  total_controls: number
  unmapped_controls: MappingControl[]
}

const SOURCES = [
  { id: 'microsoft', label: 'Microsoft 365' },
  { id: 'aws', label: 'AWS' },
  { id: 'gcp', label: 'Google Cloud' },
  { id: 'google_workspace', label: 'Google Workspace' },
]

const severityColour: Record<string, string> = {
  critical: '#B91C1C',
  high: '#EF4444',
  medium: '#F59E0B',
  low: '#64748B',
}

const filterLabel = (value: 'all' | 'mapped' | 'unmapped') => {
  if (value === 'all') return 'All'
  if (value === 'mapped') return 'Mapped'
  return 'Unmapped'
}

export default function ZeroTrustMappingPage() {
  const [source, setSource] = useState('microsoft')
  const [filter, setFilter] = useState<'all' | 'mapped' | 'unmapped'>('all')
  const [search, setSearch] = useState('')

  const { data, isLoading, isError } = useQuery<Mapping>({
    queryKey: ['zerotrust', 'mapping', source],
    queryFn: () => zerotrustApi.mapping(source),
  })

  const rows = useMemo(() => {
    if (!data) return []
    const needle = search.trim().toLowerCase()
    return data.tests.filter((test) => {
      if (filter === 'mapped' && test.controls.length === 0) return false
      if (filter === 'unmapped' && test.controls.length > 0) return false
      if (!needle) return true
      return (
        test.check_id.toLowerCase().includes(needle) ||
        test.title.toLowerCase().includes(needle) ||
        test.controls.some((control) => control.id.toLowerCase().includes(needle))
      )
    })
  }, [data, filter, search])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Zero Trust Mapping</h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)', margin: 0 }}>
          Every test in a platform catalogue and the UniMonitor control whose collected evidence answers it.
          A test with no control is an architecture gap; a control with no test is evidence nothing is tracking.
          Controls are linked to their findings; the full framework lists live under Compliance.
        </p>
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {SOURCES.map((item) => (
          <button key={item.id} onClick={() => setSource(item.id)} style={chip(source === item.id)}>
            {item.label}
          </button>
        ))}
      </div>

      {isLoading && <div style={muted}>Loading mapping…</div>}
      {isError && <div style={muted}>The mapping is unavailable.</div>}

      {data && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10 }}>
            <Stat label="Catalogue" value={data.catalogue} />
            <Stat label="Tests" value={String(data.total_tests)} />
            <Stat label="Mapped tests" value={`${data.mapped_tests} of ${data.total_tests}`} />
            <Stat label="Unmapped tests" value={String(data.unmapped_tests)} />
            <Stat label="Controls" value={String(data.total_controls)} />
          </div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <div style={{ position: 'relative', flex: '1 1 260px' }}>
              <Search size={14} style={{ position: 'absolute', left: 10, top: 10, color: 'var(--color-text-muted)' }} />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search test, id or control…"
                style={{ ...inputStyle, paddingLeft: 30 }}
              />
            </div>
            {(['all', 'mapped', 'unmapped'] as const).map((value) => (
              <button key={value} onClick={() => setFilter(value)} style={chip(filter === value)}>
                {filterLabel(value)}
              </button>
            ))}
          </div>

          <div style={{ border: '1px solid var(--color-border)', borderRadius: 10, overflow: 'hidden' }}>
            <div style={{ ...rowStyle, background: 'var(--color-surface-2)', fontSize: 11, color: 'var(--color-text-muted)' }}>
              <span style={{ minWidth: 108 }}>Test</span>
              <span style={{ flex: 2 }}>Title</span>
              <span style={{ flex: 1, minWidth: 140 }}>Pillar</span>
              <span style={{ flex: 2, minWidth: 220 }}>Evidence from</span>
            </div>
            {rows.length === 0 && <div style={muted}>No tests match this filter.</div>}
            {rows.map((test) => (
              <div key={test.check_id} style={rowStyle}>
                <span style={{ minWidth: 108, fontSize: 11, fontFamily: 'monospace', color: 'var(--color-text-muted)' }}>
                  {test.check_id}
                </span>
                <span style={{ flex: 2, fontSize: 12 }}>
                  {test.title}
                  <span style={{ marginLeft: 8, fontSize: 10, color: severityColour[test.severity] ?? '#64748B' }}>
                    {test.severity}
                  </span>
                </span>
                <span style={{ flex: 1, minWidth: 140, fontSize: 11, color: 'var(--color-text-muted)' }}>{test.pillar}</span>
                <span style={{ flex: 2, minWidth: 220, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                  {test.controls.length === 0 ? (
                    <>
                      <CircleSlash size={13} color="#EF4444" />
                      <span style={{ fontSize: 11, color: '#EF4444' }}>No control collects this evidence</span>
                    </>
                  ) : (
                    test.controls.map((control) => (
                      <Link
                        key={control.id}
                        to={`/findings?control=${encodeURIComponent(control.id)}`}
                        title={control.title}
                        style={controlChip}
                      >
                        {control.id}
                      </Link>
                    ))
                  )}
                </span>
              </div>
            ))}
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <CheckCircle2 size={16} color={data.unmapped_controls.length ? '#F59E0B' : '#10B981'} />
              <h2 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>
                Controls with no catalogue test ({data.unmapped_controls.length})
              </h2>
            </div>
            <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 0 }}>
              Their findings are still evaluated and shown in the assessment, but no Zero Trust test consumes them.
            </p>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {data.unmapped_controls.length === 0 && <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>Every control maps to at least one test.</span>}
              {data.unmapped_controls.map((control) => (
                <Link key={control.id} to={`/findings?control=${encodeURIComponent(control.id)}`} style={controlChip} title={control.title}>
                  {control.id}
                </Link>
              ))}
            </div>
          </div>

          <Link
            to={`/zero-trust/platform/${source}`}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--color-brand)' }}
          >
            Open the {data.platform} architecture page <ArrowRight size={13} />
          </Link>
        </>
      )}
    </div>
  )
}

function Stat({ label, value }: Readonly<{ label: string; value: string }>) {
  return (
    <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 10, padding: 12 }}>
      <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.5, color: 'var(--color-text-muted)' }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 600, marginTop: 4 }}>{value}</div>
    </div>
  )
}

const rowStyle: React.CSSProperties = {
  display: 'flex',
  gap: 12,
  alignItems: 'center',
  padding: '9px 12px',
  borderBottom: '1px solid var(--color-border)',
}

const controlChip: React.CSSProperties = {
  fontSize: 10,
  fontFamily: 'monospace',
  padding: '2px 7px',
  borderRadius: 999,
  border: '1px solid var(--color-border)',
  color: 'var(--color-text)',
  textDecoration: 'none',
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 10px',
  fontSize: 12,
  borderRadius: 7,
  border: '1px solid var(--color-border)',
  background: 'var(--color-surface-2)',
  color: 'var(--color-text)',
  outline: 'none',
  boxSizing: 'border-box',
}

const muted: React.CSSProperties = { padding: 14, fontSize: 12, color: 'var(--color-text-muted)' }

const chip = (active: boolean): React.CSSProperties => ({
  padding: '5px 10px',
  fontSize: 11,
  borderRadius: 999,
  cursor: 'pointer',
  border: `1px solid ${active ? 'var(--color-brand)' : 'var(--color-border)'}`,
  background: active ? 'var(--color-brand)' : 'var(--color-surface)',
  color: active ? '#fff' : 'var(--color-text)',
})
