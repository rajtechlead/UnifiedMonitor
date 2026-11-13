import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { reportsApi } from '../hooks/useApi'
import { FileText, Download, Plus, CheckCircle, Clock, Loader, XCircle } from 'lucide-react'

type Report = {
  id: string
  report_type: string
  formats: string[]
  status: string
  file_paths?: Record<string, string>
  created_at: string
  requested_by: string
  run_id?: string
}

type RunReportSummary = {
  run_id: string
  assessment_id: string
  tenant_id: string
  status: string
  security_score: number | null
  compliance_score: number | null
  total_controls_checked: number
  controls_passed: number
  critical_count: number
  high_count: number
  started_at: string
  completed_at: string | null
  report_id: string | null
  report_status: string | null
}

const FORMAT_OPTIONS = ['pdf', 'excel', 'csv', 'json']
const FORMAT_LABELS: Record<string, string> = {
  pdf: 'PDF Report', excel: 'Excel Workbook', csv: 'CSV Export', json: 'JSON Data',
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'completed') return <CheckCircle size={14} color="#10B981" />
  if (status === 'failed') return <XCircle size={14} color="#EF4444" />
  if (status === 'generating') return <Loader size={14} color="var(--color-brand)" />
  return <Clock size={14} color="#F59E0B" />
}

export default function ReportsPage() {
  const [showNew, setShowNew] = useState(false)
  const [selectedRunId, setSelectedRunId] = useState('')
  const [selectedFormats, setSelectedFormats] = useState<string[]>(['pdf', 'excel'])
  const qc = useQueryClient()

  const { data: reports, isLoading } = useQuery<{ items: Report[] }>({
    queryKey: ['reports'],
    queryFn: () => reportsApi.list(),
    refetchInterval: 10000, // poll while generating
  })

  // Get completed assessment runs for the run selector
  const { data: runsData } = useQuery<{ items: RunReportSummary[]; total: number }>({
    queryKey: ['report-runs'],
    queryFn: () => reportsApi.listRuns(),
    enabled: showNew,
  })

  const generateMutation = useMutation({
    mutationFn: () => reportsApi.generate(selectedRunId, selectedFormats),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reports'] })
      setShowNew(false)
      setSelectedRunId('')
    },
  })

  const handleDownload = async (id: string, format: string) => {
    try {
      const res = await reportsApi.download(id, format)
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `unimonitor-report-${id.slice(0, 8)}.${format === 'excel' ? 'xlsx' : format}`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      alert('Download failed. The report may not be ready yet.')
    }
  }

  const reportList: Report[] = (reports?.items ?? []) as Report[]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Reports</h1>
          <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
            Generate and download compliance and security reports
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
          <Plus size={14} /> Generate Report
        </button>
      </div>

      {/* Generate form */}
      {showNew && (
        <div style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-brand)',
          borderRadius: 12, padding: 20,
        }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Generate New Report</div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>
              Assessment Run
            </label>
            <select
              value={selectedRunId}
              onChange={e => setSelectedRunId(e.target.value)}
              style={{
                width: '100%', padding: '9px 12px', fontSize: 13,
                border: '1px solid var(--color-border)', borderRadius: 7,
                background: 'var(--color-surface-2)', color: 'var(--color-text)', outline: 'none',
              }}
            >
              <option value="">Select a completed run…</option>
              {(runsData?.items || []).map((run: RunReportSummary) => (
                <option key={run.run_id} value={run.run_id}>
                  {new Date(run.started_at).toLocaleDateString()} —{' '}
                  {run.total_controls_checked} controls
                  {run.security_score != null ? ` · Score ${run.security_score.toFixed(0)}%` : ''}
                  {run.report_id ? ' ✓ Report ready' : ''}
                </option>
              ))}
            </select>
            <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 4 }}>
              Run an assessment first to generate a report from its findings.
            </div>
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 8 }}>
              Output Formats
            </label>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              {FORMAT_OPTIONS.map(fmt => (
                <label key={fmt} style={{
                  display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer',
                  padding: '8px 14px', borderRadius: 8, fontSize: 13,
                  border: `1px solid ${selectedFormats.includes(fmt) ? 'var(--color-brand)' : 'var(--color-border)'}`,
                  background: selectedFormats.includes(fmt) ? 'rgba(23,118,210,0.1)' : 'var(--color-surface-2)',
                }}>
                  <input
                    type="checkbox"
                    checked={selectedFormats.includes(fmt)}
                    onChange={e => setSelectedFormats(prev =>
                      e.target.checked ? [...prev, fmt] : prev.filter(f => f !== fmt)
                    )}
                    style={{ display: 'none' }}
                  />
                  <FileText size={14} color={selectedFormats.includes(fmt) ? 'var(--color-brand)' : 'var(--color-text-muted)'} />
                  <span style={{ color: selectedFormats.includes(fmt) ? 'var(--color-brand)' : 'var(--color-text-muted)' }}>
                    {FORMAT_LABELS[fmt]}
                  </span>
                </label>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', gap: 10 }}>
            <button
              onClick={() => generateMutation.mutate()}
              disabled={!selectedRunId || selectedFormats.length === 0 || generateMutation.isPending}
              style={{
                padding: '7px 16px', fontSize: 13, background: 'var(--color-brand)',
                color: 'white', border: 'none', borderRadius: 6, cursor: 'pointer',
                opacity: (!selectedRunId || selectedFormats.length === 0) ? 0.5 : 1,
              }}
            >
              {generateMutation.isPending ? 'Queuing…' : 'Generate Report'}
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

      {/* Reports list */}
      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 48, color: 'var(--color-text-muted)', fontSize: 13 }}>
          Loading reports…
        </div>
      ) : reportList.length === 0 ? (
        <div style={{
          textAlign: 'center', padding: 64,
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 12, color: 'var(--color-text-muted)', fontSize: 13,
        }}>
          No reports generated yet.
        </div>
      ) : (
        <div style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 12, overflow: 'hidden',
        }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)', background: 'var(--color-surface-2)' }}>
                {['Status', 'Type', 'Formats', 'Requested By', 'Created', 'Downloads'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '10px 14px',
                    fontWeight: 600, color: 'var(--color-text-muted)', fontSize: 12 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {reportList.map((r) => (
                <tr key={r.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '12px 14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <StatusIcon status={r.status} />
                      <span style={{ textTransform: 'capitalize' }}>{r.status}</span>
                    </div>
                  </td>
                  <td style={{ padding: '12px 14px', textTransform: 'capitalize' }}>
                    {r.report_type?.replace('_', ' ')}
                  </td>
                  <td style={{ padding: '12px 14px' }}>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {(r.formats || []).map(fmt => (
                        <span key={fmt} style={{
                          fontSize: 10, padding: '1px 6px', borderRadius: 3,
                          background: 'var(--color-surface-2)', color: 'var(--color-text-muted)',
                          textTransform: 'uppercase',
                        }}>{fmt}</span>
                      ))}
                    </div>
                  </td>
                  <td style={{ padding: '12px 14px', color: 'var(--color-text-muted)' }}>
                    {r.requested_by}
                  </td>
                  <td style={{ padding: '12px 14px', color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
                    {new Date(r.created_at).toLocaleString()}
                  </td>
                  <td style={{ padding: '12px 14px' }}>
                    {r.status === 'completed' ? (
                      <div style={{ display: 'flex', gap: 6 }}>
                        {(r.formats || []).map(fmt => (
                          <button
                            key={fmt}
                            onClick={() => handleDownload(r.id, fmt)}
                            style={{
                              padding: '4px 10px', fontSize: 11,
                              background: 'transparent',
                              border: '1px solid var(--color-border)', borderRadius: 5,
                              color: 'var(--color-brand)', cursor: 'pointer',
                              display: 'flex', alignItems: 'center', gap: 4,
                            }}
                          >
                            <Download size={11} />
                            {fmt.toUpperCase()}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>—</span>
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
