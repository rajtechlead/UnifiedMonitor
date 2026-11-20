import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, ShieldCheck } from 'lucide-react'
import { grcApi } from '../hooks/useApi'

type Evidence = {
  type: string
  source: string
  content: string
  collected_at: string
}

type FrameworkControl = {
  control_id: string
  external_id: string
  name: string
  category: string
  severity: string
  state: string
  last_seen: string | null
  finding_id: string | null
  remediation: string
  evidence: Evidence[]
}

const STATE_LABELS: Record<string, string> = {
  implemented: 'Met',
  partially_implemented: 'Partially met',
  not_implemented: 'Not met',
  not_applicable: 'Not applicable',
  not_run: 'No evidence',
}

const stateColour: Record<string, string> = {
  implemented: '#10B981',
  partially_implemented: '#F59E0B',
  not_implemented: '#EF4444',
  not_applicable: '#64748B',
  not_run: 'var(--color-text-muted)',
}

export default function FrameworkPage() {
  const { frameworkId = '' } = useParams()
  const [stateFilter, setStateFilter] = useState('')
  const [search, setSearch] = useState('')

  const { data: frameworks } = useQuery({
    queryKey: ['grc', 'frameworks'],
    queryFn: grcApi.frameworks,
  })
  const { data: controls, isLoading, isError } = useQuery<FrameworkControl[]>({
    queryKey: ['grc', 'framework-controls', frameworkId],
    queryFn: () => grcApi.frameworkControls(frameworkId),
    enabled: Boolean(frameworkId),
  })

  const framework = (frameworks as Array<{ framework_id: string; framework_name: string }> | undefined)
    ?.find(f => f.framework_id === frameworkId)

  const rows = useMemo(() => {
    const list = controls ?? []
    const query = search.trim().toLowerCase()
    return list.filter(c =>
      (!stateFilter || c.state === stateFilter) &&
      (!query || c.name.toLowerCase().includes(query) || c.external_id.toLowerCase().includes(query))
    )
  }, [controls, stateFilter, search])

  const counts = useMemo(() => {
    const list = controls ?? []
    return {
      total: list.length,
      met: list.filter(c => c.state === 'implemented').length,
      partial: list.filter(c => c.state === 'partially_implemented').length,
      notMet: list.filter(c => c.state === 'not_implemented').length,
      noEvidence: list.filter(c => c.state === 'not_run').length,
    }
  }, [controls])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <Link to="/compliance" style={{ fontSize: 12, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <ArrowLeft size={13} /> All frameworks
        </Link>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: '8px 0 4px' }}>
          {framework?.framework_name ?? frameworkId}
        </h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          Every control mapped to this framework, and the evidence behind each result.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12 }}>
        {[
          { label: 'Mapped controls', value: counts.total, colour: 'var(--color-brand)' },
          { label: 'Met', value: counts.met, colour: '#10B981' },
          { label: 'Partially met', value: counts.partial, colour: '#F59E0B' },
          { label: 'Not met', value: counts.notMet, colour: '#EF4444' },
          { label: 'No evidence', value: counts.noEvidence, colour: 'var(--color-text-muted)' },
        ].map(card => (
          <div key={card.label} style={{
            background: 'var(--color-surface)', border: '1px solid var(--color-border)',
            borderRadius: 10, padding: 16, textAlign: 'center',
          }}>
            <div style={{ fontSize: 24, fontWeight: 700, color: card.colour }}>{card.value}</div>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 4 }}>{card.label}</div>
          </div>
        ))}
      </div>

      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 10, padding: 14, display: 'flex', gap: 12, flexWrap: 'wrap',
      }}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search controls…"
          aria-label="Search controls"
          style={{
            flex: 1, minWidth: 200, padding: '7px 10px', fontSize: 13, borderRadius: 6,
            border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
            color: 'var(--color-text)', outline: 'none',
          }}
        />
        <select
          value={stateFilter}
          onChange={e => setStateFilter(e.target.value)}
          aria-label="Filter by result"
          style={{
            padding: '6px 10px', borderRadius: 6, fontSize: 13,
            border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
            color: 'var(--color-text)',
          }}
        >
          {['', 'implemented', 'partially_implemented', 'not_implemented', 'not_run'].map(state => (
            <option key={state} value={state}>{state ? STATE_LABELS[state] : 'All results'}</option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>Loading controls…</div>
      ) : isError ? (
        <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          Could not load this framework's controls. Check that the API is reachable.
        </div>
      ) : rows.length === 0 ? (
        <div style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 12, padding: 40, textAlign: 'center', fontSize: 13, color: 'var(--color-text-muted)',
        }}>
          No controls match these filters.
        </div>
      ) : (
        <div style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 12, overflow: 'hidden',
        }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: 'var(--color-surface-2)', borderBottom: '1px solid var(--color-border)' }}>
                {['Control', 'Category', 'Severity', 'Result', 'Evidence', ''].map(header => (
                  <th key={header} style={{
                    textAlign: 'left', padding: '10px 14px', fontSize: 12, fontWeight: 600,
                    color: 'var(--color-text-muted)',
                  }}>{header}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(control => (
                <tr key={control.external_id} style={{ borderBottom: '1px solid var(--color-border)', verticalAlign: 'top' }}>
                  <td style={{ padding: '10px 14px', maxWidth: 320 }}>
                    <div style={{ fontWeight: 500 }}>{control.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
                      {control.external_id}
                    </div>
                  </td>
                  <td style={{ padding: '10px 14px', color: 'var(--color-text-muted)' }}>{control.category}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span className={`severity-chip severity-${control.severity}`}>{control.severity}</span>
                  </td>
                  <td style={{ padding: '10px 14px', color: stateColour[control.state] || 'inherit', fontWeight: 600 }}>
                    {STATE_LABELS[control.state] ?? control.state}
                  </td>
                  <td style={{ padding: '10px 14px', maxWidth: 380 }}>
                    {control.evidence.length === 0 ? (
                      <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                        {control.state === 'not_run'
                          ? 'No collection has evaluated this control yet.'
                          : 'Collected without a stored evidence record.'}
                      </span>
                    ) : (
                      control.evidence.map(item => (
                        <div key={`${item.source}-${item.collected_at}`} style={{ marginBottom: 6 }}>
                          <div style={{ fontSize: 11, fontWeight: 600 }}>
                            <ShieldCheck size={11} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                            {item.source}
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--color-text-muted)', whiteSpace: 'pre-wrap' }}>
                            {item.content.slice(0, 400)}
                          </div>
                        </div>
                      ))
                    )}
                  </td>
                  <td style={{ padding: '10px 14px', whiteSpace: 'nowrap' }}>
                    {control.finding_id && (
                      <Link to={`/findings?finding=${control.finding_id}`} style={{ fontSize: 12 }}>
                        Remediation →
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
