import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { ArrowRight, Play, ShieldQuestion } from 'lucide-react'
import { zerotrustApi } from '../hooks/useApi'

type Check = { check_id: string; title: string; pillar: string; status: string; severity: string; remediation: string[] }
type Platform = {
  source: string
  platform: string
  has_run: boolean
  score: number
  total: number
  passed: number
  failed: number
  not_run: number
  last_run: string | null
  pillars: { id: string; name: string; score: number; total: number; failed: number }[]
}
type Summary = { platforms: Platform[] }

type GapControl = {
  id: string
  title: string
  service: string
  pillar: string
  collector: string
  expected_keys: string[]
  missing_keys: string[]
  uncollected_keys: string[]
  state: string | null
  has_finding: boolean
  has_evidence: boolean
}
type GapTest = { check_id: string; title: string; pillar: string; reason: string; controls: GapControl[] }
type PlatformGaps = {
  source: string
  platform: string
  tests_total: number
  tests_evidenced: number
  controls_total: number
  controls_lacking: number
  gaps: GapTest[]
  controls: GapControl[]
}
type GapsResponse = { platforms: PlatformGaps[] }

const statusColour: Record<string, string> = {
  pass: '#10B981',
  fail: '#EF4444',
  warn: '#F59E0B',
  not_run: '#94A3B8',
  not_applicable: '#94A3B8',
}

const sourceFor = (platform?: string) =>
  ['microsoft', 'aws', 'gcp', 'google_workspace'].includes(platform ?? '') ? (platform as string) : 'microsoft'

export default function ZeroTrustPlatformPage() {
  const params = useParams()
  const source = sourceFor(params.platform)
  const queryClient = useQueryClient()
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const summary = useQuery<Summary>({ queryKey: ['zerotrust', 'summary'], queryFn: zerotrustApi.summary })
  const gaps = useQuery<GapsResponse>({
    queryKey: ['zerotrust', 'gaps', source],
    queryFn: () => zerotrustApi.evidenceGaps(source),
  })
  const checks = useQuery<Check[]>({
    queryKey: ['zerotrust', 'checks', source],
    queryFn: () => zerotrustApi.checks({ source }),
  })

  const platform = summary.data?.platforms.find((item) => item.source === source)
  const coverage = gaps.data?.platforms[0]
  const failing = (checks.data ?? []).filter((check) => check.status === 'fail' || check.status === 'warn')

  const evaluate = async () => {
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await zerotrustApi.evaluate(source)
      setMessage(`Evaluated ${result.run.total} checks — score ${Math.round(result.run.score)}%.`)
      await queryClient.invalidateQueries({ queryKey: ['zerotrust'] })
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Could not evaluate this platform.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>
          {platform?.platform ?? 'Zero Trust'} architecture
        </h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)', margin: 0 }}>
          The platform's Zero Trust tests, the UniMonitor controls behind them, and exactly which evidence the
          collectors still have to return.
        </p>
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <button onClick={evaluate} disabled={busy} style={primaryButton}>
          <Play size={14} /> {busy ? 'Evaluating…' : `Evaluate ${platform?.platform ?? source}`}
        </button>
        <Link to="/zero-trust/mapping" style={secondaryLink}>Test-to-control mapping <ArrowRight size={13} /></Link>
        <Link to="/zero-trust/assessment" style={secondaryLink}>Assessment table <ArrowRight size={13} /></Link>
      </div>
      {message && <div style={{ fontSize: 12, color: '#10B981' }}>{message}</div>}
      {error && <div style={{ fontSize: 12, color: '#EF4444' }}>{error}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 10 }}>
        <Stat label="Score" value={platform?.has_run ? `${Math.round(platform.score)}%` : '—'} />
        <Stat label="Tests" value={String(coverage?.tests_total ?? platform?.total ?? 0)} />
        <Stat label="With evidence" value={String(coverage?.tests_evidenced ?? 0)} />
        <Stat label="Controls lacking" value={String(coverage?.controls_lacking ?? 0)} />
        <Stat label="Failing / investigate" value={String(failing.length)} />
      </div>

      {platform && platform.pillars.filter((pillar) => pillar.total > 0).length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 10 }}>
          {platform.pillars
            .filter((pillar) => pillar.total > 0)
            .map((pillar) => (
              <div key={pillar.id} style={cardStyle}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontWeight: 600 }}>
                  <span>{pillar.name}</span>
                  <span style={{ color: statusColour[pillar.failed ? 'warn' : 'pass'] }}>{Math.round(pillar.score)}%</span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 4 }}>
                  {pillar.total} tests · {pillar.failed} failing
                </div>
              </div>
            ))}
        </div>
      )}

      <section style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <h2 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>Evidence gaps</h2>
        <p style={{ fontSize: 12, color: 'var(--color-text-muted)', margin: 0 }}>
          Tests no control can currently answer, or whose control has no collected data. Fix these by extending the
          named collector or by filling the posture snapshot.
        </p>
        <div style={{ border: '1px solid var(--color-border)', borderRadius: 10, overflow: 'hidden' }}>
          {gaps.isLoading && <div style={muted}>Loading gaps…</div>}
          {!gaps.isLoading && (coverage?.gaps.length ?? 0) === 0 && (
            <div style={muted}>Every test has collector evidence.</div>
          )}
          {(coverage?.gaps ?? []).slice(0, 60).map((gap) => (
            <div key={gap.check_id} style={{ padding: '10px 12px', borderBottom: '1px solid var(--color-border)' }}>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <ShieldQuestion size={14} color="#F59E0B" />
                <span style={{ fontSize: 11, fontFamily: 'monospace', color: 'var(--color-text-muted)', minWidth: 108 }}>
                  {gap.check_id}
                </span>
                <span style={{ flex: 1, fontSize: 12 }}>{gap.title}</span>
                <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{gap.pillar}</span>
              </div>
              <div style={{ fontSize: 11, color: '#F59E0B', marginTop: 4 }}>{gap.reason}</div>
              {gap.controls.map((control) => (
                <div key={control.id} style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 3 }}>
                  <Link to={`/findings?control=${encodeURIComponent(control.id)}`} style={{ color: 'var(--color-text)' }}>
                    {control.id}
                  </Link>{' '}
                  · collector: {control.collector}
                  {control.expected_keys.length > 0 && <> · expects {control.expected_keys.join(', ')}</>}
                  {control.missing_keys.length > 0 && (
                    <span style={{ color: '#EF4444' }}> · missing {control.missing_keys.join(', ')}</span>
                  )}
                  {control.uncollected_keys.length > 0 && (
                    <span style={{ color: '#EF4444' }}>
                      {' '}· no collector yet for {control.uncollected_keys.join(', ')}
                    </span>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      </section>

      <section style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <h2 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>Controls and their evidence</h2>
        <div style={{ border: '1px solid var(--color-border)', borderRadius: 10, overflow: 'hidden' }}>
          {(coverage?.controls ?? []).map((control) => (
            <div key={control.id} style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '8px 12px', borderBottom: '1px solid var(--color-border)' }}>
              <span style={{ fontSize: 11, fontFamily: 'monospace', color: 'var(--color-text-muted)', minWidth: 120 }}>{control.id}</span>
              <span style={{ flex: 1, fontSize: 12 }}>{control.title}</span>
              <span style={{ fontSize: 11, color: 'var(--color-text-muted)', minWidth: 190 }}>{control.collector}</span>
              <span style={{ fontSize: 11, minWidth: 96, textAlign: 'right', color: statusColour[
                control.state === 'implemented' ? 'pass' : control.state === 'not_implemented' ? 'fail' : control.state === 'partially_implemented' ? 'warn' : 'not_run'
              ] }}>
                {control.has_evidence ? control.state ?? 'collected' : 'no evidence'}
              </span>
            </div>
          ))}
        </div>
      </section>

      {platform?.last_run && (
        <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
          Last run {new Date(platform.last_run).toLocaleString()}
        </div>
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div style={cardStyle}>
      <div style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.5, color: 'var(--color-text-muted)' }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, marginTop: 4 }}>{value}</div>
    </div>
  )
}

const cardStyle: React.CSSProperties = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  borderRadius: 10,
  padding: 12,
}

const primaryButton: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 12px', fontSize: 12,
  borderRadius: 7, border: 0, background: 'var(--color-brand)', color: '#fff', cursor: 'pointer',
}

const secondaryLink: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 12px', fontSize: 12,
  borderRadius: 7, border: '1px solid var(--color-border)', background: 'var(--color-surface)',
  color: 'var(--color-text)', textDecoration: 'none',
}

const muted: React.CSSProperties = { padding: 14, fontSize: 12, color: 'var(--color-text-muted)' }
