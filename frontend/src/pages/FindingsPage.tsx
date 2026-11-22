import { Fragment, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
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
  remediation: string | null
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

function AiGuidanceButton({ findingId }: Readonly<{ findingId: string }>) {
  const qc = useQueryClient()
  const mutation = useMutation({
    mutationFn: () => findingsApi.aiRemediate(findingId, true),
    onSuccess: () => {
      // The run is queued (or already done in-process); refresh the list shortly after.
      setTimeout(() => void qc.invalidateQueries({ queryKey: ['findings'] }), 2500)
    },
  })

  return (
    <div style={{ marginTop: 8 }}>
      <button
        type="button"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
        style={{
          padding: '5px 12px', fontSize: 12, background: 'var(--color-brand)', color: 'white',
          border: 'none', borderRadius: 6, cursor: mutation.isPending ? 'not-allowed' : 'pointer',
          opacity: mutation.isPending ? 0.7 : 1,
        }}
      >
        {mutation.isPending ? 'Asking the model…' : 'Generate AI guidance'}
      </button>
      {mutation.isError && (
        <div style={{ fontSize: 11, color: '#EF4444', marginTop: 4 }}>
          AI guidance could not be started. Check the configured providers in Settings.
        </div>
      )}
      {mutation.isSuccess && (
        <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 4 }}>
          {mutation.data?.message || 'AI guidance requested — reopen the finding in a few seconds.'}
        </div>
      )}
    </div>
  )
}

function Timeline({ findingId }: Readonly<{ findingId: string }>) {
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
  // Links from the SOC, Risk and Compliance views land on a pre-filtered list.
  const [searchParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const [severity, setSeverity] = useState(() => (searchParams.get('severity') || '').toUpperCase())
  const [state, setState] = useState(() => searchParams.get('state') || '')
  const [triage, setTriage] = useState('')
  const [category, setCategory] = useState('')
  const [sortBy, setSortBy] = useState('last_seen_at')
  const [sortDesc, setSortDesc] = useState(true)

  const sortArrow = (column: string) => {
    if (sortBy !== column) return ''
    return sortDesc ? ' ▼' : ' ▲'
  }
  const [page, setPage] = useState(1)
  const [expandedId, setExpandedId] = useState<string | null>(() => searchParams.get('finding'))
  const pageSize = 25
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery<FindingListResponse>({
    queryKey: ['findings', { search, severity, state, triage, category, sortBy, sortDesc, page }],
    queryFn: () => findingsApi.list({
      search: search || undefined,
      severity: severity || undefined,
      state: state || undefined,
      triage_status: triage || undefined,
      category: category || undefined,
      sort_by: sortBy,
      sort_desc: sortDesc,
      page,
      page_size: pageSize,
    }),
    placeholderData: (prev) => prev,
  })

  const { data: summary } = useQuery<{ by_category: Record<string, number> }>({
    queryKey: ['findings-summary'],
    queryFn: () => findingsApi.summary(),
  })

  const toggleSort = (column: string) => {
    if (sortBy === column) {
      setSortDesc(!sortDesc)
    } else {
      setSortBy(column)
      setSortDesc(column !== 'title' && column !== 'external_control_id')
    }
    setPage(1)
  }

  const { data: priority } = useQuery<{ items: PriorityItem[] }>({
    queryKey: ['finding-priority'],
    queryFn: () => findingsApi.priority(),
  })

  const findings: Finding[] = data?.items || []
  const total: number = data?.total || 0
  const totalPages = data?.pages || 1

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['findings'] })
    void queryClient.invalidateQueries({ queryKey: ['finding-priority'] })
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
        <select value={category} onChange={e => { setCategory(e.target.value); setPage(1) }} style={selectStyle}>
          <option value="">All Categories</option>
          {Object.keys(summary?.by_category ?? {}).sort((a, b) => a.localeCompare(b)).map(cat => (
            <option key={cat} value={cat}>{cat}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, overflow: 'hidden',
      }}>
        {isLoading && (
          <div style={{ textAlign: 'center', padding: 48, color: 'var(--color-text-muted)', fontSize: 13 }}>
            Loading findings…
          </div>
        )}
        {!isLoading && findings.length === 0 && (
          <div style={{ textAlign: 'center', padding: 48, color: 'var(--color-text-muted)', fontSize: 13 }}>
            No findings match your filters.
          </div>
        )}
        {!isLoading && findings.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)', background: 'var(--color-surface-2)' }}>
                <th style={{ width: 24 }} />
                {[
                  { label: 'Control', sort: 'external_control_id' },
                  { label: 'Title', sort: 'title' },
                  { label: 'Severity', sort: 'severity' },
                  { label: 'Category', sort: 'category' },
                  { label: 'State', sort: 'state' },
                  { label: 'Triage', sort: 'triage_status' },
                ].map(({ label, sort }) => (
                  <th
                    key={label}
                    onClick={() => toggleSort(sort)}
                    title={`Sort by ${label.toLowerCase()}`}
                    style={{ textAlign: 'left', padding: '10px 14px', cursor: 'pointer', userSelect: 'none',
                      fontWeight: 600, color: sortBy === sort ? 'var(--color-brand)' : 'var(--color-text-muted)', fontSize: 12 }}
                  >
                    {label}{sortArrow(sort)}
                  </th>
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
                              {f.remediation || remediationText(f.ai_remediation)}
                            </div>
                            {typeof f.ai_remediation?.source === 'string' && (
                              <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 4 }}>
                                Generated by {String(f.ai_remediation.source)}
                              </div>
                            )}
                            <AiGuidanceButton findingId={f.id} />
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
