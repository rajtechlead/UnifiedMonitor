import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Cloud, Database, KeyRound, ShieldAlert, Boxes, Route, Bot } from 'lucide-react'
import { api } from '../hooks/useApi'

type Finding = {
  id: string
  title: string
  severity: string
  category: string
  resource: string
  detail: string
  remediation: string
  steps?: string[]
}

type Engine = {
  category: string
  label: string
  risk_score: number
  summary: { total: number; by_severity: Record<string, number> }
  findings: Finding[]
  note?: string
}

type Benchmark = {
  platform: string
  benchmark_name?: string
  score: number | null
  passed: number
  failed: number
  evaluated: number
  results: { id: string; title: string; severity: string; state: string; detail: string; remediation: string }[]
}

type Analysis = {
  platform: string | null
  inventory: { resources: number; edges: number; by_type: Record<string, number> }
  benchmarks: Benchmark[]
  engines: Record<string, Engine>
  findings: Finding[]
  summary: { total: number; by_severity: Record<string, number> }
  risk_score: number
}

const PLATFORMS = [
  { value: '', label: 'All benchmarks' },
  { value: 'aws', label: 'AWS' },
  { value: 'azure', label: 'Azure' },
  { value: 'gcp', label: 'Google Cloud' },
  { value: 'm365', label: 'Microsoft 365' },
  { value: 'google_workspace', label: 'Google Workspace' },
]

const ENGINE_ICONS: Record<string, React.ElementType> = {
  dspm: Database,
  ciem: KeyRound,
  aispm: Bot,
  kubernetes: Boxes,
  paths: Route,
}

const SEVERITY_COLOUR: Record<string, string> = {
  critical: '#DC2626',
  high: '#EA580C',
  medium: '#D97706',
  low: '#2563EB',
  informational: '#64748B',
}

function ScoreCard({ label, value }: Readonly<{ label: string; value: string }>) {
  return (
    <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 12, padding: 18 }}>
      <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700 }}>{value}</div>
    </div>
  )
}

function FindingRow({ finding }: Readonly<{ finding: Finding }>) {
  return (
    <div style={{ borderTop: '1px solid var(--color-border)', padding: '12px 0' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: SEVERITY_COLOUR[finding.severity] || 'inherit' }}>
          {finding.severity}
        </span>
        <span style={{ fontSize: 13, fontWeight: 600 }}>{finding.title}</span>
      </div>
      <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
        <strong>{finding.resource}</strong> — {finding.detail}
      </div>
      {finding.steps && (
        <ol style={{ margin: '6px 0 0 18px', padding: 0, fontSize: 12, color: 'var(--color-text-muted)' }}>
          {finding.steps.map((step) => <li key={step}>{step}</li>)}
        </ol>
      )}
      {finding.remediation && (
        <div style={{ fontSize: 12, marginTop: 4 }}><strong>Fix:</strong> {finding.remediation}</div>
      )}
    </div>
  )
}

function EngineCard({ engine }: Readonly<{ engine: Engine }>) {
  const Icon = ENGINE_ICONS[engine.category] || ShieldAlert
  return (
    <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 12, padding: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon size={16} color="var(--color-brand)" />
          <span style={{ fontSize: 14, fontWeight: 600 }}>{engine.label}</span>
        </div>
        <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{engine.summary.total} findings</span>
      </div>
      {engine.note && <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{engine.note}</div>}
      {engine.findings.map((finding) => <FindingRow key={`${finding.id}-${finding.resource}`} finding={finding} />)}
    </div>
  )
}

export default function PosturePage() {
  const [platform, setPlatform] = useState('')
  const { data, isLoading, isError, error } = useQuery<Analysis>({
    queryKey: ['posture', platform],
    queryFn: () => api.get('/posture/analysis', { params: platform ? { platform } : {} }).then((response) => response.data),
    retry: false,
  })

  const status = (error as { response?: { status?: number; data?: { detail?: string } } })?.response

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Cloud size={18} /> Cloud Posture
          </h1>
          <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
            CIS benchmark packs, data exposure, entitlements, AI deployments, Kubernetes and attack paths — analysed from the
            inventory snapshot, not live credentials.
          </p>
        </div>
        <select
          value={platform}
          onChange={(event) => setPlatform(event.target.value)}
          style={{
            padding: '8px 12px', fontSize: 13, border: '1px solid var(--color-border)',
            borderRadius: 7, background: 'var(--color-surface-2)', color: 'var(--color-text)', outline: 'none',
          }}
        >
          {PLATFORMS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </div>

      {isLoading && <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>Analysing the snapshot…</div>}

      {isError && (
        <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 12, padding: 24, fontSize: 13 }}>
          {status?.status === 404
            ? (status.data?.detail || 'No posture snapshot is configured.')
            : 'The posture analysis could not be loaded.'}
        </div>
      )}

      {data && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
            <ScoreCard label="Posture score (relative)" value={`${data.risk_score}/100`} />
            <ScoreCard label="Findings" value={String(data.summary.total)} />
            <ScoreCard label="Critical + high" value={String((data.summary.by_severity.critical || 0) + (data.summary.by_severity.high || 0))} />
            <ScoreCard label="Inventory resources" value={String(data.inventory.resources)} />
          </div>

          {data.benchmarks.length > 0 && (
            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 12, padding: 20 }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>CIS benchmark packs (indicative)</div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ textAlign: 'left', color: 'var(--color-text-muted)', fontSize: 12 }}>
                    <th style={{ padding: '6px 8px' }}>Benchmark</th>
                    <th style={{ padding: '6px 8px' }}>Score</th>
                    <th style={{ padding: '6px 8px' }}>Passed</th>
                    <th style={{ padding: '6px 8px' }}>Failed</th>
                    <th style={{ padding: '6px 8px' }}>Not applicable</th>
                  </tr>
                </thead>
                <tbody>
                  {data.benchmarks.map((benchmark) => (
                    <tr key={benchmark.platform} style={{ borderTop: '1px solid var(--color-border)' }}>
                      <td style={{ padding: '8px' }}>{benchmark.benchmark_name || benchmark.platform}</td>
                      <td style={{ padding: '8px' }}>{benchmark.score === null ? '—' : `${benchmark.score}%`}</td>
                      <td style={{ padding: '8px' }}>{benchmark.passed}</td>
                      <td style={{ padding: '8px' }}>{benchmark.failed}</td>
                      <td style={{ padding: '8px' }}>{benchmark.results.filter((rule) => rule.state === 'not_applicable').length}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 8 }}>
                Rule ids are internal and implement benchmark intent; they are not an official CIS attestation.
              </div>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 16 }}>
            {Object.values(data.engines).map((engine) => <EngineCard key={engine.category} engine={engine} />)}
          </div>

          {data.findings.length > 0 && (
            <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 12, padding: 20 }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>All findings, highest severity first</div>
              {data.findings.map((finding) => <FindingRow key={`${finding.category}-${finding.id}-${finding.resource}`} finding={finding} />)}
            </div>
          )}
        </>
      )}
    </div>
  )
}
