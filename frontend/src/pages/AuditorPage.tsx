import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Download, FileSearch } from 'lucide-react'
import { api, grcApi } from '../hooks/useApi'

type FrameworkRow = {
  framework_id: string
  framework_name: string
  coverage_pct: number
  controls_total: number
  controls_implemented: number
}

type RequirementRow = {
  id: string
  title: string
  family: string
  level: number
  level_name: string
  source: string
  controls_total: number
  implemented: number
  partial: number
  not_implemented: number
  coverage_pct: number
  status: string
}

type RequirementCatalogue = {
  framework_id: string
  framework_name: string
  catalogue: string
  levels: { level: number; name: string }[]
  requirement_count: number
  level1_count: number
  rows: RequirementRow[]
}

function catalogueSourceLabel(catalogue: RequirementCatalogue | null): string {
  if (!catalogue) return ''
  if (catalogue.catalogue === 'official') return 'Official requirement catalogue'
  if (catalogue.catalogue === 'mapping') return 'Mapped measures'
  return 'Requirement view derived from control mappings'
}

const cardStyle = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  borderRadius: 12,
  padding: 20,
}

const statusColor = (status: string) => {
  if (status === 'implemented') return '#10B981'
  if (status === 'partial') return '#F59E0B'
  if (status === 'not_run') return 'var(--color-text-muted)'
  return '#EF4444'
}

export default function AuditorPage() {
  const [frameworkId, setFrameworkId] = useState('cpcsc')
  const [level, setLevel] = useState(0)
  const [downloading, setDownloading] = useState(false)
  const [message, setMessage] = useState('')

  const { data: frameworks } = useQuery<FrameworkRow[]>({
    queryKey: ['grc', 'frameworks'],
    queryFn: grcApi.frameworks,
  })

  const { data: catalogue, isError: catalogueError } = useQuery<RequirementCatalogue>({
    queryKey: ['grc', 'requirements', frameworkId, level],
    queryFn: () =>
      api
        .get(`/grc/frameworks/${frameworkId}/requirements`, { params: level ? { level } : undefined })
        .then((r) => r.data),
  })

  const download = async () => {
    setDownloading(true)
    setMessage('')
    try {
      const response = await api.get(`/grc/frameworks/${frameworkId}/evidence-package`, { responseType: 'blob' })
      const url = URL.createObjectURL(response.data as Blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `unimonitor-evidence-${frameworkId}.json`
      link.click()
      URL.revokeObjectURL(url)
      setMessage('Evidence package downloaded. Its digest is inside the file.')
    } catch {
      setMessage('Could not build the evidence package. Auditor and compliance roles can download it.')
    } finally {
      setDownloading(false)
    }
  }

  const rows = catalogue?.rows ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Auditor portal</h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          Read-only evidence for assessors: requirement status and a hashed, self-contained package per framework.
        </p>
      </div>

      <div style={{ ...cardStyle, display: 'flex', alignItems: 'flex-end', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <label htmlFor="auditor-framework" style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 6 }}>
            FRAMEWORK
          </label>
          <select
            id="auditor-framework"
            value={frameworkId}
            onChange={(e) => setFrameworkId(e.target.value)}
            style={{
              padding: '9px 12px', fontSize: 13, borderRadius: 7, minWidth: 280,
              border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
              color: 'var(--color-text)', cursor: 'pointer',
            }}
          >
            {(frameworks ?? []).map((framework) => (
              <option key={framework.framework_id} value={framework.framework_id}>
                {framework.framework_name} — {Math.round(framework.coverage_pct)}% ({framework.controls_total} controls)
              </option>
            ))}
            {!frameworks && <option value="cpcsc">CPCSC</option>}
          </select>
        </div>
        <button
          onClick={download}
          disabled={downloading}
          style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: '9px 16px', fontSize: 13,
            background: 'var(--color-brand)', color: 'white', border: 'none', borderRadius: 8,
            cursor: downloading ? 'not-allowed' : 'pointer', opacity: downloading ? 0.7 : 1,
          }}
        >
          <Download size={14} /> {downloading ? 'Building…' : 'Download evidence package'}
        </button>
        {message && <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{message}</span>}
      </div>

      {(
        <div style={{ ...cardStyle, padding: 0, overflow: 'hidden' }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '16px 20px', borderBottom: '1px solid var(--color-border)', gap: 12, flexWrap: 'wrap',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <FileSearch size={16} color="var(--color-brand)" />
              <span style={{ fontSize: 14, fontWeight: 600 }}>
                {catalogue ? `${catalogue.requirement_count} requirements · ${catalogue.level1_count} at Level 1` : 'Requirement status'}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {catalogue && (
                <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
                  {catalogueSourceLabel(catalogue)}
                </span>
              )}
              <select
                aria-label="Filter by level"
                value={level}
                onChange={(e) => setLevel(Number(e.target.value))}
                style={{
                  padding: '6px 10px', fontSize: 12, borderRadius: 6,
                  border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
                  color: 'var(--color-text)', cursor: 'pointer',
                }}
              >
                <option value={0}>All levels</option>
                {(catalogue?.levels ?? []).map((item) => (
                  <option key={item.level} value={item.level}>{item.name}</option>
                ))}
              </select>
            </div>
          </div>
          {catalogueError && (
            <p style={{ padding: 20, fontSize: 13, color: 'var(--color-text-muted)' }}>
              Requirement status is available to auditor, compliance and admin roles.
            </p>
          )}
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--color-text-muted)', fontSize: 11, textTransform: 'uppercase' }}>
                {['Requirement', 'Family', 'Level', 'Coverage', 'Evidence controls'].map((heading) => (
                  <th key={heading} style={{ padding: '10px 16px', borderBottom: '1px solid var(--color-border)', fontWeight: 600 }}>
                    {heading}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '10px 16px' }}>
                    <div style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--color-text-muted)' }}>{row.id}</div>
                    <div style={{ fontWeight: 500 }}>{row.title}</div>
                  </td>
                  <td style={{ padding: '10px 16px', color: 'var(--color-text-muted)' }}>{row.family}</td>
                  <td style={{ padding: '10px 16px' }}>{row.level_name || row.level}</td>
                  <td style={{ padding: '10px 16px', color: statusColor(row.status), fontWeight: 600 }}>
                    {Math.round(row.coverage_pct)}%
                    <span style={{ marginLeft: 6, fontSize: 11, fontWeight: 400, color: 'var(--color-text-muted)' }}>
                      {row.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td style={{ padding: '10px 16px', color: 'var(--color-text-muted)', fontSize: 12 }}>
                    {row.implemented} implemented · {row.partial} partial · {row.not_implemented} open of {row.controls_total}
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
