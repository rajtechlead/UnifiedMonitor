import { useMemo, useRef, useState, type CSSProperties } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { AlertTriangle, ArrowRight, CheckCircle2, ChevronDown, ChevronRight, Download, Play, Search, Upload } from 'lucide-react'
import { zerotrustApi } from '../hooks/useApi'

type Check = {
  check_id: string
  title: string
  pillar: string
  severity: string
  status: 'pass' | 'fail' | 'warn' | 'not_run' | 'not_applicable'
  category: string | null
  remediation: string[]
  reference: string | null
}

type Platform = {
  source: string
  platform: string
  has_run: boolean
  score: number
  total: number
  passed: number
  failed: number
  warned: number
  not_run: number
  last_run: string | null
  pillars: { id: string; name: string; score: number; total: number; failed: number }[]
}

type Summary = { platforms: Platform[]; overall_score: number }

const statusColour: Record<string, string> = {
  pass: '#10B981',
  fail: '#EF4444',
  warn: '#F59E0B',
  not_run: '#94A3B8',
  not_applicable: '#94A3B8',
}

const statusLabel: Record<string, string> = {
  pass: 'Passed',
  fail: 'Failed',
  warn: 'Investigate',
  not_run: 'Not run',
  not_applicable: 'N/A',
}

const SEVERITY_COLOURS: Record<string, string> = {
  critical: '#B91C1C',
  high: '#EF4444',
  medium: '#F59E0B',
}

const severityColour = (severity: string) => SEVERITY_COLOURS[severity] ?? '#64748B'

function scoreColour(score: number): string {
  if (score >= 70) return statusColour.pass
  if (score >= 50) return statusColour.warn
  return statusColour.fail
}

function platformCaption(platform: Platform): string {
  if (!platform.has_run) return 'No assessment yet'
  const unrun = platform.not_run ? ` · ${platform.not_run} not run` : ''
  return `${platform.passed} passed · ${platform.failed} failed${unrun}`
}

function emptyChecksMessage(hasRun: boolean, isMicrosoft: boolean): string {
  if (hasRun) return 'No checks match these filters.'
  if (isMicrosoft) return 'Run the Python assessment, or import a ZeroTrustAssessmentReport.json as a manual fallback.'
  return 'Select Evaluate now to score this platform from collected evidence.'
}

export default function ZeroTrustAssessmentPage() {
  const queryClient = useQueryClient()
  const fileInput = useRef<HTMLInputElement>(null)
  const [source, setSource] = useState('microsoft')
  const [pillar, setPillar] = useState('')
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const summary = useQuery<Summary>({
    queryKey: ['zerotrust', 'summary'],
    queryFn: zerotrustApi.summary,
  })

  const checks = useQuery<Check[]>({
    queryKey: ['zerotrust', 'checks', source, pillar, status, search],
    queryFn: () => zerotrustApi.checks({
      source,
      ...(pillar ? { pillar } : {}),
      ...(status ? { status } : {}),
      ...(search ? { q: search } : {}),
    }),
  })

  const selected = summary.data?.platforms.find((platform) => platform.source === source)
  const pillars = useMemo(() => selected?.pillars.filter((p) => p.total > 0) ?? [], [selected])

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['zerotrust'] })
  }

  const importReport = async (file: File) => {
    setError(''); setMessage(''); setBusy(true)
    try {
      const payload = JSON.parse(await file.text())
      const result = await zerotrustApi.importReport(payload)
      setMessage(`Imported ${result.run.total} checks — score ${result.run.score}%.`)
      setSource('microsoft')
      await refresh()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'That file is not a Zero Trust Assessment JSON report.')
    } finally {
      setBusy(false)
      if (fileInput.current) fileInput.current.value = ''
    }
  }

  const evaluate = async () => {
    setError(''); setMessage(''); setBusy(true)
    try {
      const result = await zerotrustApi.evaluate(source)
      setMessage(`Evaluated ${result.run.total} ${selected?.platform ?? source} checks — score ${result.run.score}%.`)
      await refresh()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Could not evaluate this platform.')
    } finally {
      setBusy(false)
    }
  }

  const evaluateAll = async () => {
    setError(''); setMessage(''); setBusy(true)
    try {
      const result = await zerotrustApi.evaluateAll()
      const scored = result.runs as Array<{ platform?: string; source: string; score: number }>
      setMessage(
        `Evaluated ${scored.length} platform(s): ` +
        scored.map((run) => `${run.source} ${Math.round(run.score)}%`).join(', ') +
        (result.skipped.length ? ` · skipped ${result.skipped.join(', ')}` : '')
      )
      await refresh()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Could not evaluate the platforms.')
    } finally {
      setBusy(false)
    }
  }

  const downloadScript = async () => {
    setError('')
    try {
      const text = await zerotrustApi.script()
      const url = URL.createObjectURL(new Blob([text], { type: 'text/plain' }))
      const link = document.createElement('a')
      link.href = url
      link.download = 'Invoke-UniMonitorZeroTrust.ps1'
      link.click()
      URL.revokeObjectURL(url)
    } catch {
      setError('The PowerShell runner is not bundled with this build.')
    }
  }

  const isMicrosoft = source === 'microsoft'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Zero Trust Assessment</h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)', margin: 0 }}>
          One Python assessment engine scores Microsoft 365, AWS, Google Cloud and Google Workspace from
          collected evidence, with remediation guidance on every result. The PowerShell runner stays
          available as a manual fallback.
        </p>
      </div>

      {/* Platform cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
        {(summary.data?.platforms ?? []).map((platform) => (
          <button
            key={platform.source}
            onClick={() => { setSource(platform.source); setPillar(''); setStatus(''); setExpanded(null) }}
            style={{
              textAlign: 'left', cursor: 'pointer', padding: 14, borderRadius: 10,
              border: `1px solid ${platform.source === source ? 'var(--color-brand)' : 'var(--color-border)'}`,
              background: 'var(--color-surface)', color: 'var(--color-text)',
              display: 'flex', flexDirection: 'column', gap: 6,
            }}
          >
            <span style={{ fontSize: 13, fontWeight: 600 }}>{platform.platform}</span>
            <span style={{ fontSize: 11, color: 'var(--color-brand)' }}>Open architecture page →</span>
            <span style={{ fontSize: 22, fontWeight: 700, color: platform.has_run ? scoreColour(platform.score) : '#94A3B8' }}>
              {platform.has_run ? `${Math.round(platform.score)}%` : '—'}
            </span>
            <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
              {platformCaption(platform)}
            </span>
          </button>
        ))}
      </div>

      <Link
        to={`/zero-trust/platform/${source}`}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--color-brand)' }}
      >
        Open the {selected?.platform ?? source} architecture page <ArrowRight size={13} />
      </Link>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <button onClick={evaluate} disabled={busy} style={primaryButton}>
          <Play size={14} /> {busy ? 'Evaluating…' : `Evaluate ${selected?.platform ?? 'platform'}`}
        </button>
        <button onClick={evaluateAll} disabled={busy} style={secondaryButton}>
          <Play size={14} /> Evaluate all platforms
        </button>
        {isMicrosoft && (
          <>
            <input
              ref={fileInput}
              type="file"
              accept="application/json,.json"
              style={{ display: 'none' }}
              onChange={(event) => { const file = event.target.files?.[0]; if (file) void importReport(file) }}
            />
            <button onClick={() => fileInput.current?.click()} disabled={busy} style={secondaryButton}>
              <Upload size={14} /> Import PowerShell report (manual)
            </button>
            <button onClick={downloadScript} style={secondaryButton}>
              <Download size={14} /> PowerShell runner
            </button>
          </>
        )}
        <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
          {isMicrosoft
            ? 'Python by default; the PowerShell report can still be generated on a Windows workstation and imported here.'
            : 'Runs the platform’s controls against the latest collected evidence.'}
        </span>
      </div>

      {message && <div style={{ fontSize: 12, color: '#10B981' }}>{message}</div>}
      {error && <div style={{ fontSize: 12, color: '#EF4444' }}>{error}</div>}
      {busy && <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>Evaluating…</div>}

      {/* Pillar strip */}
      {pillars.length > 0 && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button onClick={() => setPillar('')} style={chip(!pillar)}>
            All pillars ({selected?.total ?? 0})
          </button>
          {pillars.map((item) => (
            <button key={item.id} onClick={() => setPillar(item.id)} style={chip(pillar === item.id)}>
              {item.name} · {Math.round(item.score)}%
            </button>
          ))}
        </div>
      )}

      {/* Filters */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: '1 1 240px' }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: 10, color: 'var(--color-text-muted)' }} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search checks or ids…"
            style={{ ...inputStyle, paddingLeft: 30 }}
          />
        </div>
        <select value={status} onChange={(event) => setStatus(event.target.value)} style={{ ...inputStyle, flex: '0 0 150px' }}>
          <option value="">Any status</option>
          <option value="fail">Failed</option>
          <option value="warn">Investigate</option>
          <option value="pass">Passed</option>
          <option value="not_run">Not run</option>
        </select>
      </div>

      {/* Checks */}
      <div style={{ border: '1px solid var(--color-border)', borderRadius: 10, overflow: 'hidden' }}>
        {checks.isLoading && <div style={emptyStyle}>Loading checks…</div>}
        {!checks.isLoading && (checks.data?.length ?? 0) === 0 && (
          <div style={emptyStyle}>{emptyChecksMessage(Boolean(selected?.has_run), isMicrosoft)}</div>
        )}
        {(checks.data ?? []).map((check) => {
          const open = expanded === check.check_id
          return (
            <div key={check.check_id} style={{ borderBottom: '1px solid var(--color-border)' }}>
              <button
                onClick={() => setExpanded(open ? null : check.check_id)}
                style={{
                  width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
                  background: 'transparent', border: 0, cursor: 'pointer', textAlign: 'left', color: 'var(--color-text)',
                }}
              >
                {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                {check.status === 'pass' ? (
                  <CheckCircle2 size={14} color={statusColour.pass} />
                ) : (
                  <AlertTriangle size={14} color={statusColour[check.status]} />
                )}
                <span style={{ fontSize: 12, fontFamily: 'monospace', color: 'var(--color-text-muted)', minWidth: 78 }}>
                  {check.check_id}
                </span>
                <span style={{ flex: 1, fontSize: 13 }}>{check.title}</span>
                <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 999, border: `1px solid ${severityColour(check.severity)}`, color: severityColour(check.severity) }}>
                  {check.severity}
                </span>
                <span style={{ fontSize: 11, color: statusColour[check.status], minWidth: 74, textAlign: 'right' }}>
                  {statusLabel[check.status] ?? check.status}
                </span>
              </button>

              {open && (
                <div style={{ padding: '2px 12px 14px 40px', fontSize: 12, color: 'var(--color-text-muted)' }}>
                  <div style={{ marginBottom: 8 }}>
                    <strong style={{ color: 'var(--color-text)' }}>Pillar:</strong> {check.pillar}
                    {check.category ? <> · <strong style={{ color: 'var(--color-text)' }}>Category:</strong> {check.category}</> : null}
                  </div>
                  {check.remediation.length > 0 ? (
                    <>
                      <div style={{ fontWeight: 600, color: 'var(--color-text)', marginBottom: 4 }}>Remediation</div>
                      <ol style={{ margin: 0, paddingLeft: 18, lineHeight: 1.7 }}>
                        {check.remediation.map((step) => <li key={`${check.check_id}:${step}`}>{step}</li>)}
                      </ol>
                    </>
                  ) : (
                    <div>No remediation guidance was included with this result.</div>
                  )}
                  {check.reference && (
                    <a href={check.reference} target="_blank" rel="noreferrer" style={{ display: 'inline-block', marginTop: 8 }}>
                      Reference
                    </a>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {selected?.last_run && (
        <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
          Last run {new Date(selected.last_run).toLocaleString()} · {selected.platform}
        </div>
      )}
    </div>
  )
}

const primaryButton: CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 12px', fontSize: 12,
  borderRadius: 7, border: 0, background: 'var(--color-brand)', color: '#fff', cursor: 'pointer',
}

const secondaryButton: CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 12px', fontSize: 12,
  borderRadius: 7, border: '1px solid var(--color-border)', background: 'var(--color-surface)',
  color: 'var(--color-text)', cursor: 'pointer',
}

const inputStyle: CSSProperties = {
  width: '100%', padding: '8px 10px', fontSize: 12, borderRadius: 7,
  border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
  color: 'var(--color-text)', outline: 'none', boxSizing: 'border-box',
}

const emptyStyle: CSSProperties = {
  padding: 18, fontSize: 12, color: 'var(--color-text-muted)', background: 'var(--color-surface)',
}

const chip = (active: boolean): CSSProperties => ({
  padding: '5px 10px', fontSize: 11, borderRadius: 999, cursor: 'pointer',
  border: `1px solid ${active ? 'var(--color-brand)' : 'var(--color-border)'}`,
  background: active ? 'var(--color-brand)' : 'var(--color-surface)',
  color: active ? '#fff' : 'var(--color-text)',
})
