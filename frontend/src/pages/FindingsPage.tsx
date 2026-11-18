import { Fragment, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { findingsApi } from '../hooks/useApi'
import { Search, ChevronDown, ChevronUp, TrendingUp } from 'lucide-react'

type Finding = {
  id: string
  external_control_id: string
  title: string
  description: string
  severity: string
  state: string
  triage_status: string
  category: string
  service: string
  risk_score: number
  ai_remediation: Record<string, unknown> | null
  first_detected_at: string
  last_seen_at: string
}

type FindingListResponse = {
  items: Finding[]
  total: number
  page: number
  page_size: number
  pages: number
}

type PriorityItem = {
  id: string
  external_control_id: string
  title: string
  severity: string
  effort: number
  impact: number
  roi: number
}

type TimelineItem = {
  kind: string
  at: string
  state?: string
  source?: string
  detail?: string
}

const SEVERITIES = ['', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFORMATIONAL']
const STATES = ['', 'implemented', 'partially_implemented', 'not_implemented', 'not_applicable']
const TRIAGE = ['', 'open', 'acknowledged', 'snoozed', 'resolved']

const selectStyle: React.CSSProperties = {
  padding: '6px 10px', borderRadius: 6, fontSize: 13,
  border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
  color: 'var(--color-text)', cursor: 'pointer',
}

function remediationText(value: Finding['ai_remediation']): string {
  if (!value) return 'AI remediation guidance not yet generated.'
  for (const key of ['summary', 'plan', 'steps', 'recommendation']) {
    const candidate = value[key]
    if (typeof candidate === 'string') return candidate
    if (Array.isArray(candidate)) return candidate.map(String).join('\n')
  }
  return JSON.stringify(value, null, 2)
}

function Timeline({ findingId }: { findingId: string }) {
  const { data, isLoading } = useQuery<TimelineItem[]>({
    queryKey: ['finding-timeline', findingId],
    queryFn: () => findingsApi.timeline(findingId),
  })

  if (isLoading) return <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>Loading timeline…</div>
  if (!data || data.length === 0) return <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>No timeline events yet.</div>

  return (
    <ol style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
      {data.map((item, index) => (
        <li key={`${item.at}-${index}`} style={{ display: 'flex', gap: 10, fontSize: 12 }}>
          <span style={{ color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
            {new Date(item.at).toLocaleString()}
          </span>
          <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>{item.kind}</span>
          <span style={{ color: 'var(--color-text-muted)' }}>{item.detail || item.source || item.state}</span>
        </li>
      ))}
    </ol>
  )
}

export default function FindingsPage() {
  const [search, setSearch] = useState('')
  const [severity, setSeverity] = useState('')
  const [state, setState] = useState('')
  const [triage, setTriage] = useState('')
  const [page, setPage] = useState(1)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const pageSize = 25
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery<FindingListResponse>({
    queryKey: ['findings', { search, severity, state, triage, page }],
    queryFn: () => findingsApi.list({
      search: search || undefined,
      severity: severity || undefined,
      state: state || undefined,
      triage_status: triage || undefined,
      page,
      page_size: pageSize,
    }),
    placeholderData: (prev) => prev,
  })

  const { data: priority } = useQuery<{ items: PriorityItem[] }>({
    queryKey: ['finding-priority'],
    queryFn: () => findingsApi.priority(),
  })

  const findings: Finding[] = data?.items || []
  const total: number = data?.total || 0
  const totalPages = data?.pages || 1

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['findings'] })
    queryClient.invalidateQueries({ queryKey: ['finding-priority'] })
  }

  const handleTriage = async (id: string, status: string) => {
    try {
      await findingsApi.triage(id, { status })
      refresh()
    } catch {
      // best-effort; the row keeps its previous value
    }
  }

  const handleStateChange = async (id: string, newState: string) => {
    try {
      await findingsApi.updateState(id, newState)
      refresh()
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

      {/* Remediation priority queue */}
      {priority && priority.items.length > 0 && (
        <div style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 12, padding: 16,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <TrendingUp size={16} color="var(--color-brand)" />
            <span style={{ fontSize: 14, fontWeight: 600 }}>Fix first</span>
            <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
              highest impact per unit of remediation effort
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {priority.items.slice(0, 5).map((item, index) => (
              <div key={item.id} style={{
                display: 'grid', gridTemplateColumns: '24px 110px 1fr 80px 60px 60px',
                gap: 10, alignItems: 'center', fontSize: 12,
              }}>
                <span style={{ color: 'var(--color-text-muted)' }}>{index + 1}</span>
                <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{item.external_control_id}</span>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.title}</span>
                <span className={`severity-chip severity-${item.severity?.toLowerCase()}`}>{item.severity}</span>
                <span style={{ color: 'var(--color-text-muted)' }}>effort {item.effort}</span>
                <span style={{ fontWeight: 600 }}>ROI {item.roi}</span>
              </div>
            ))}
          </div>
        </div>
      )}

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
        <select value={severity} onChange={e => { setSeverity(e.target.value); setPage(1) }} style={selectStyle}>
          {SEVERITIES.map(s => (
            <option key={s} value={s}>{s || 'All Severities'}</option>
          ))}
        </select>
        <select value={state} onChange={e => { setState(e.target.value); setPage(1) }} style={selectStyle}>
          {STATES.map(s => (
            <option key={s} value={s}>{s ? s.replace(/_/g, ' ') : 'All States'}</option>
          ))}
        </select>
        <select value={triage} onChange={e => { setTriage(e.target.value); setPage(1) }} style={selectStyle}>
          {TRIAGE.map(s => (
            <option key={s} value={s}>{s ? s.replace(/_/g, ' ') : 'All Triage'}</option>
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
                {['', 'Control', 'Title', 'Severity', 'Category', 'State', 'Triage'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '10px 14px',
                    fontWeight: 600, color: 'var(--color-text-muted)', fontSize: 12 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {findings.map((f) => (
                <Fragment key={f.id}>
                  <tr
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
                      {f.external_control_id}
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
                      {f.category}
                    </td>
                    <td style={{ padding: '10px 14px' }} onClick={e => e.stopPropagation()}>
                      <select
                        value={f.state}
                        onChange={e => handleStateChange(f.id, e.target.value)}
                        style={{ ...selectStyle, padding: '3px 6px', fontSize: 11 }}
                      >
                        {STATES.filter(Boolean).map(s => (
                          <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
                        ))}
                      </select>
                    </td>
                    <td style={{ padding: '10px 14px' }} onClick={e => e.stopPropagation()}>
                      <select
                        value={f.triage_status || 'open'}
                        onChange={e => handleTriage(f.id, e.target.value)}
                        style={{ ...selectStyle, padding: '3px 6px', fontSize: 11 }}
                      >
                        {TRIAGE.filter(Boolean).map(s => (
                          <option key={s} value={s}>{s}</option>
                        ))}
                      </select>
                    </td>
                  </tr>
                  {expandedId === f.id && (
                    <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
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
                            <div style={{ fontSize: 13, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                              {remediationText(f.ai_remediation)}
                            </div>
                          </div>
                        </div>
                        <div style={{ marginTop: 16 }}>
                          <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 6 }}>
                            INVESTIGATION TIMELINE
                          </div>
                          <Timeline findingId={f.id} />
                        </div>
                        <div style={{ marginTop: 10, fontSize: 11, color: 'var(--color-text-muted)' }}>
                          Detected: {new Date(f.first_detected_at).toLocaleString()} · Last seen: {new Date(f.last_seen_at).toLocaleString()}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8 }}>
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{ ...selectStyle, opacity: page === 1 ? 0.5 : 1 }}
          >
            Previous
          </button>
          <span style={{ alignSelf: 'center', fontSize: 12, color: 'var(--color-text-muted)' }}>
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            style={{ ...selectStyle, opacity: page === totalPages ? 0.5 : 1 }}
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
