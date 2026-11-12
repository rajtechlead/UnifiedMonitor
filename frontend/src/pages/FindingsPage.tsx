import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { findingsApi } from '../hooks/useApi'
import { Search, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react'

type Finding = {
  id: string
  control_id: string
  title: string
  description: string
  severity: string
  state: string
  framework: string
  evidence_summary?: string
  remediation_summary?: string
  created_at: string
}

type FindingListResponse = {
  items: Finding[]
  total: number
  page: number
  page_size: number
}

const SEVERITIES = ['', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFORMATIONAL']
const STATES = ['', 'open', 'acknowledged', 'resolved', 'false_positive']

export default function FindingsPage() {
  const [search, setSearch] = useState('')
  const [severity, setSeverity] = useState('')
  const [state, setState] = useState('open')
  const [page, setPage] = useState(1)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const pageSize = 25

  const { data, isLoading } = useQuery<FindingListResponse>({
    queryKey: ['findings', { search, severity, state, page }],
    queryFn: () => findingsApi.list({
      search: search || undefined,
      severity: severity || undefined,
      state: state || undefined,
      limit: pageSize,
      offset: (page - 1) * pageSize,
    }),
    placeholderData: (prev) => prev,
  })

  const findings: Finding[] = data?.items || []
  const total: number = data?.total || 0
  const totalPages = Math.ceil(total / pageSize)

  const handleStateChange = async (id: string, newState: string) => {
    try {
      await findingsApi.update(id, { state: newState })
    } catch {
      // best-effort
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Findings</h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          {total} finding{total !== 1 ? 's' : ''} total
        </p>
      </div>

      {/* Filters */}
      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 10, padding: 16, display: 'flex', gap: 12, flexWrap: 'wrap',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 200 }}>
          <Search size={15} color="var(--color-text-muted)" />
          <input
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
            placeholder="Search findings…"
            style={{
              flex: 1, border: 'none', outline: 'none',
              background: 'transparent', color: 'var(--color-text)', fontSize: 13,
            }}
          />
        </div>
        <select
          value={severity}
          onChange={e => { setSeverity(e.target.value); setPage(1) }}
          style={{
            padding: '6px 10px', borderRadius: 6, fontSize: 13,
            border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
            color: 'var(--color-text)', cursor: 'pointer',
          }}
        >
          {SEVERITIES.map(s => (
            <option key={s} value={s}>{s || 'All Severities'}</option>
          ))}
        </select>
        <select
          value={state}
          onChange={e => { setState(e.target.value); setPage(1) }}
          style={{
            padding: '6px 10px', borderRadius: 6, fontSize: 13,
            border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
            color: 'var(--color-text)', cursor: 'pointer',
          }}
        >
          {STATES.map(s => (
            <option key={s} value={s}>{s || 'All States'}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, overflow: 'hidden',
      }}>
        {isLoading ? (
          <div style={{ textAlign: 'center', padding: 48, color: 'var(--color-text-muted)', fontSize: 13 }}>
            Loading findings…
          </div>
        ) : findings.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 48, color: 'var(--color-text-muted)', fontSize: 13 }}>
            No findings match your filters.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)', background: 'var(--color-surface-2)' }}>
                {['', 'Control', 'Title', 'Severity', 'Framework', 'State', 'Actions'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '10px 14px',
                    fontWeight: 600, color: 'var(--color-text-muted)', fontSize: 12 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {findings.map((f) => (
                <>
                  <tr
                    key={f.id}
                    style={{
                      borderBottom: '1px solid var(--color-border)',
                      cursor: 'pointer',
                      background: expandedId === f.id ? 'var(--color-surface-2)' : undefined,
                    }}
                    onClick={() => setExpandedId(expandedId === f.id ? null : f.id)}
                  >
                    <td style={{ padding: '10px 14px', width: 24 }}>
                      {expandedId === f.id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </td>
                    <td style={{ padding: '10px 14px', fontFamily: 'monospace', fontSize: 11, whiteSpace: 'nowrap' }}>
                      {f.control_id}
                    </td>
                    <td style={{ padding: '10px 14px', maxWidth: 300 }}>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', display: 'block', whiteSpace: 'nowrap' }}>
                        {f.title}
                      </span>
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <span className={`severity-chip severity-${f.severity?.toLowerCase()}`}>
                        {f.severity}
                      </span>
                    </td>
                    <td style={{ padding: '10px 14px', color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
                      {f.framework}
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <span style={{
                        fontSize: 11, padding: '2px 8px', borderRadius: 4,
                        background: f.state === 'open' ? 'var(--color-critical-bg)'
                          : f.state === 'resolved' ? 'rgba(16,185,129,0.1)'
                          : 'var(--color-surface-2)',
                        color: f.state === 'open' ? 'var(--color-critical)'
                          : f.state === 'resolved' ? '#10B981'
                          : 'var(--color-text-muted)',
                        textTransform: 'capitalize',
                      }}>
                        {f.state}
                      </span>
                    </td>
                    <td style={{ padding: '10px 14px' }} onClick={e => e.stopPropagation()}>
                      <select
                        value={f.state}
                        onChange={e => handleStateChange(f.id, e.target.value)}
                        style={{
                          padding: '3px 6px', fontSize: 11, borderRadius: 4,
                          border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
                          color: 'var(--color-text)', cursor: 'pointer',
                        }}
                      >
                        {STATES.filter(Boolean).map(s => (
                          <option key={s} value={s} style={{ textTransform: 'capitalize' }}>{s}</option>
                        ))}
                      </select>
                    </td>
                  </tr>
                  {expandedId === f.id && (
                    <tr key={`${f.id}-detail`} style={{ borderBottom: '1px solid var(--color-border)' }}>
                      <td colSpan={7} style={{ padding: '16px 20px', background: 'var(--color-surface-2)' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                          <div>
                            <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 6 }}>
                              DESCRIPTION
                            </div>
                            <div style={{ fontSize: 13, lineHeight: 1.6 }}>{f.description || '—'}</div>
                          </div>
                          <div>
                            <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 6 }}>
                              REMEDIATION GUIDANCE
                            </div>
                            <div style={{ fontSize: 13, lineHeight: 1.6 }}>
                              {f.remediation_summary || 'AI remediation guidance not yet generated.'}
                            </div>
                          </div>
                        </div>
                        {f.evidence_summary && (
                          <div style={{ marginTop: 12 }}>
                            <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 6 }}>
                              EVIDENCE
                            </div>
                            <div style={{ fontSize: 12, fontFamily: 'monospace', background: 'var(--color-surface)',
                              padding: 10, borderRadius: 6, border: '1px solid var(--color-border)' }}>
                              {f.evidence_summary}
                            </div>
                          </div>
                        )}
                        <div style={{ marginTop: 10, fontSize: 11, color: 'var(--color-text-muted)' }}>
                          Detected: {new Date(f.created_at).toLocaleString()}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '12px 16px', borderTop: '1px solid var(--color-border)',
            fontSize: 13, color: 'var(--color-text-muted)',
          }}>
            <span>Page {page} of {totalPages} ({total} total)</span>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                disabled={page === 1}
                onClick={() => setPage(p => p - 1)}
                style={{
                  padding: '5px 10px', fontSize: 12, borderRadius: 6,
                  border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
                  color: page === 1 ? 'var(--color-text-muted)' : 'var(--color-text)',
                  cursor: page === 1 ? 'not-allowed' : 'pointer',
                }}
              >Previous</button>
              <button
                disabled={page === totalPages}
                onClick={() => setPage(p => p + 1)}
                style={{
                  padding: '5px 10px', fontSize: 12, borderRadius: 6,
                  border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
                  color: page === totalPages ? 'var(--color-text-muted)' : 'var(--color-text)',
                  cursor: page === totalPages ? 'not-allowed' : 'pointer',
                }}
              >Next</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
