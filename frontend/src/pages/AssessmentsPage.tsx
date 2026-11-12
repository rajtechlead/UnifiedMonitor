import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { assessmentsApi } from '../hooks/useApi'
import { Play, Plus, ChevronDown, ChevronUp, Clock, CheckCircle, XCircle, Loader } from 'lucide-react'

type Assessment = {
  id: string
  name: string
  description?: string
  frameworks: string[]
  collectors: string[]
  schedule?: string
  is_active: boolean
  created_at: string
  last_run?: string
}

type AssessmentRun = {
  id: string
  status: string
  started_at?: string
  completed_at?: string
  total_controls: number
  findings_count: number
  triggered_by: string
}

const FRAMEWORK_OPTIONS = [
  'iso_27001_2022', 'nist_csf_2', 'cis_controls_v8', 'cis_m365',
  'zero_trust', 'soc2', 'pci_dss_4', 'hipaa', 'gdpr', 'cmmc_2',
]

const FRAMEWORK_LABELS: Record<string, string> = {
  iso_27001_2022: 'ISO 27001:2022', nist_csf_2: 'NIST CSF 2.0',
  cis_controls_v8: 'CIS Controls v8', cis_m365: 'CIS M365',
  zero_trust: 'Zero Trust', soc2: 'SOC 2', pci_dss_4: 'PCI-DSS 4.0',
  hipaa: 'HIPAA', gdpr: 'GDPR', cmmc_2: 'CMMC 2.0',
}

function RunStatusIcon({ status }: { status: string }) {
  if (status === 'completed') return <CheckCircle size={14} color="#10B981" />
  if (status === 'failed') return <XCircle size={14} color="#EF4444" />
  if (status === 'running') return <Loader size={14} color="var(--color-brand)" />
  return <Clock size={14} color="#F59E0B" />
}

function AssessmentCard({ a }: { a: Assessment }) {
  const [expanded, setExpanded] = useState(false)
  const qc = useQueryClient()

  const { data: runs } = useQuery({
    queryKey: ['assessments', a.id, 'runs'],
    queryFn: () => assessmentsApi.getRuns(a.id),
    enabled: expanded,
  })

  const runMutation = useMutation({
    mutationFn: () => assessmentsApi.run(a.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['assessments', a.id, 'runs'] })
    },
  })

  const runList: AssessmentRun[] = runs?.items || []

  return (
    <div style={{
      background: 'var(--color-surface)', border: '1px solid var(--color-border)',
      borderRadius: 12, overflow: 'hidden',
    }}>
      <div
        style={{
          padding: 20, display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer',
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <span style={{ fontWeight: 600, fontSize: 15 }}>{a.name}</span>
            <span style={{
              fontSize: 11, padding: '2px 7px', borderRadius: 4,
              background: a.is_active ? 'rgba(16,185,129,0.1)' : 'var(--color-surface-2)',
              color: a.is_active ? '#10B981' : 'var(--color-text-muted)',
            }}>
              {a.is_active ? 'Active' : 'Inactive'}
            </span>
            {a.schedule && (
              <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>⏱ {a.schedule}</span>
            )}
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {a.frameworks.map(fw => (
              <span key={fw} style={{
                fontSize: 10, padding: '1px 6px', borderRadius: 3,
                background: 'rgba(23,118,210,0.1)', color: 'var(--color-brand)',
              }}>
                {FRAMEWORK_LABELS[fw] || fw}
              </span>
            ))}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {a.last_run && (
            <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
              Last: {new Date(a.last_run).toLocaleDateString()}
            </span>
          )}
          <button
            onClick={e => { e.stopPropagation(); runMutation.mutate() }}
            disabled={runMutation.isPending}
            style={{
              padding: '6px 14px', fontSize: 12, background: 'var(--color-brand)',
              color: 'white', border: 'none', borderRadius: 6,
              cursor: runMutation.isPending ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', gap: 6,
              opacity: runMutation.isPending ? 0.7 : 1,
            }}
          >
            <Play size={12} />
            {runMutation.isPending ? 'Starting…' : 'Run Now'}
          </button>
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </div>

      {expanded && (
        <div style={{ borderTop: '1px solid var(--color-border)', padding: '16px 20px' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: 10 }}>
            RECENT RUNS
          </div>
          {runList.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>No runs yet.</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                  {['Status', 'Started', 'Duration', 'Controls', 'Findings', 'Triggered By'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '6px 10px',
                      fontWeight: 600, color: 'var(--color-text-muted)', fontSize: 11 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {runList.map((r) => {
                  const duration = r.started_at && r.completed_at
                    ? Math.round((new Date(r.completed_at).getTime() - new Date(r.started_at).getTime()) / 1000)
                    : null
                  return (
                    <tr key={r.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                      <td style={{ padding: '8px 10px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <RunStatusIcon status={r.status} />
                          <span style={{ textTransform: 'capitalize' }}>{r.status}</span>
                        </div>
                      </td>
                      <td style={{ padding: '8px 10px', color: 'var(--color-text-muted)' }}>
                        {r.started_at ? new Date(r.started_at).toLocaleString() : '—'}
                      </td>
                      <td style={{ padding: '8px 10px', color: 'var(--color-text-muted)' }}>
                        {duration !== null ? `${duration}s` : '—'}
                      </td>
                      <td style={{ padding: '8px 10px' }}>{r.total_controls}</td>
                      <td style={{ padding: '8px 10px' }}>{r.findings_count}</td>
                      <td style={{ padding: '8px 10px', color: 'var(--color-text-muted)', textTransform: 'capitalize' }}>
                        {r.triggered_by}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

export default function AssessmentsPage() {
  const [showNew, setShowNew] = useState(false)
  const [newName, setNewName] = useState('')
  const [newFrameworks, setNewFrameworks] = useState<string[]>(['iso_27001_2022', 'cis_m365'])
  const qc = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['assessments'],
    queryFn: assessmentsApi.list,
  })

  const createMutation = useMutation({
    mutationFn: () => assessmentsApi.create({
      name: newName,
      frameworks: newFrameworks,
      collectors: [],
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['assessments'] })
      setShowNew(false)
      setNewName('')
    },
  })

  const assessments: Assessment[] = data?.items || []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Assessments</h1>
          <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
            {assessments.length} assessment{assessments.length !== 1 ? 's' : ''} configured
          </p>
        </div>
        <button
          onClick={() => setShowNew(!showNew)}
          style={{
            padding: '8px 16px', fontSize: 13, background: 'var(--color-brand)',
            color: 'white', border: 'none', borderRadius: 8,
            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
          }}
        >
          <Plus size={14} /> New Assessment
        </button>
      </div>

      {/* New assessment form */}
      {showNew && (
        <div style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-brand)',
          borderRadius: 12, padding: 20,
        }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Create New Assessment</div>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Name</label>
            <input
              value={newName}
              onChange={e => setNewName(e.target.value)}
              placeholder="e.g. Quarterly M365 Assessment"
              style={{
                width: '100%', padding: '9px 12px', fontSize: 13,
                border: '1px solid var(--color-border)', borderRadius: 7,
                background: 'var(--color-surface-2)', color: 'var(--color-text)', outline: 'none',
              }}
            />
          </div>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 8 }}>Frameworks</label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {FRAMEWORK_OPTIONS.map(fw => (
                <label key={fw} style={{
                  display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer',
                  padding: '4px 10px', borderRadius: 6, fontSize: 12,
                  border: `1px solid ${newFrameworks.includes(fw) ? 'var(--color-brand)' : 'var(--color-border)'}`,
                  background: newFrameworks.includes(fw) ? 'rgba(23,118,210,0.1)' : 'var(--color-surface-2)',
                  color: newFrameworks.includes(fw) ? 'var(--color-brand)' : 'var(--color-text-muted)',
                }}>
                  <input
                    type="checkbox"
                    checked={newFrameworks.includes(fw)}
                    onChange={e => setNewFrameworks(prev =>
                      e.target.checked ? [...prev, fw] : prev.filter(f => f !== fw)
                    )}
                    style={{ display: 'none' }}
                  />
                  {FRAMEWORK_LABELS[fw] || fw}
                </label>
              ))}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              onClick={() => createMutation.mutate()}
              disabled={!newName || newFrameworks.length === 0 || createMutation.isPending}
              style={{
                padding: '7px 16px', fontSize: 13, background: 'var(--color-brand)',
                color: 'white', border: 'none', borderRadius: 6, cursor: 'pointer',
                opacity: (!newName || newFrameworks.length === 0) ? 0.5 : 1,
              }}
            >
              {createMutation.isPending ? 'Creating…' : 'Create Assessment'}
            </button>
            <button
              onClick={() => setShowNew(false)}
              style={{
                padding: '7px 16px', fontSize: 13, background: 'transparent',
                color: 'var(--color-text-muted)', border: '1px solid var(--color-border)',
                borderRadius: 6, cursor: 'pointer',
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 48, color: 'var(--color-text-muted)', fontSize: 13 }}>
          Loading assessments…
        </div>
      ) : assessments.length === 0 ? (
        <div style={{
          textAlign: 'center', padding: 64,
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 12, color: 'var(--color-text-muted)', fontSize: 13,
        }}>
          No assessments configured yet. Create your first one to get started.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {assessments.map(a => <AssessmentCard key={a.id} a={a} />)}
        </div>
      )}
    </div>
  )
}
