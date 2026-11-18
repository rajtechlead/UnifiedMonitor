import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Clock, Play, RefreshCw } from 'lucide-react'
import { monitoringApi } from '../hooks/useApi'

type Schedule = {
  enabled: boolean
  interval_minutes: number
  next_run: string
  last_run: string | null
  collectors: number
}

type Collector = {
  name: string
  display_name: string
  description: string
  provider: string
  last_run: string | null
  last_status: string | null
  enabled: boolean
}

type HistoryRun = {
  id: string
  assessment_name: string
  trigger: string
  status: string
  started_at: string
  completed_at: string | null
  total_controls_checked: number
  security_score: number | null
}

const card = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  borderRadius: 12,
  padding: 18,
}

export default function CollectionPage() {
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const queryClient = useQueryClient()

  const { data: schedule } = useQuery<Schedule>({
    queryKey: ['monitoring', 'schedule'],
    queryFn: monitoringApi.schedule,
  })
  const { data: collectors, isLoading } = useQuery<Collector[]>({
    queryKey: ['monitoring', 'collectors'],
    queryFn: monitoringApi.collectors,
  })
  const { data: history } = useQuery<HistoryRun[]>({
    queryKey: ['monitoring', 'history'],
    queryFn: monitoringApi.history,
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['monitoring'] })
  }

  const act = async (key: string, action: () => Promise<unknown>, done: string) => {
    setBusy(key)
    setMessage('')
    try {
      await action()
      setMessage(done)
      refresh()
    } catch {
      setMessage('The request failed. Check that a Celery worker is running and the platform is connected.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Data Collection</h1>
          <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
            Collect on a schedule or run a collector by hand.
          </p>
        </div>
        <button
          onClick={() => act('all', () => monitoringApi.collect(), 'Full collection queued.')}
          disabled={busy !== null}
          style={{ padding: '8px 14px', fontSize: 13, borderRadius: 8, border: 'none',
            background: 'var(--color-brand)', color: 'white', cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 6, opacity: busy ? 0.6 : 1 }}
        >
          <RefreshCw size={14} /> Collect now
        </button>
      </div>

      {message && (
        <div style={{ fontSize: 12, padding: '10px 12px', borderRadius: 8,
          background: 'var(--color-surface-2)', border: '1px solid var(--color-border)' }}>
          {message}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14 }}>
        <div style={card}>
          <div style={{ fontSize: 12, color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Clock size={13} /> Automatic collection
          </div>
          <div style={{ fontSize: 18, fontWeight: 700, marginTop: 6 }}>
            {schedule?.enabled ? `Every ${schedule.interval_minutes} min` : 'Disabled'}
          </div>
          <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 4 }}>
            {schedule?.enabled
              ? `Next run around ${new Date(schedule.next_run).toLocaleTimeString()}`
              : 'Set AUTO_COLLECTION=true to enable'}
          </div>
        </div>
        <div style={card}>
          <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>Last collection</div>
          <div style={{ fontSize: 18, fontWeight: 700, marginTop: 6 }}>
            {schedule?.last_run ? new Date(schedule.last_run).toLocaleString() : 'Never'}
          </div>
        </div>
        <div style={card}>
          <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>Collectors</div>
          <div style={{ fontSize: 18, fontWeight: 700, marginTop: 6 }}>{schedule?.collectors ?? collectors?.length ?? 0}</div>
        </div>
      </div>

      <div style={card}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Collectors</div>
        {isLoading ? (
          <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>Loading collectors…</div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 10 }}>
            {(collectors || []).map((collector) => (
              <div key={collector.name} style={{ border: '1px solid var(--color-border)',
                borderRadius: 8, padding: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{collector.display_name}</span>
                  <button
                    onClick={() => act(collector.name, () => monitoringApi.runCollector(collector.name),
                      `${collector.display_name} queued.`)}
                    disabled={busy !== null}
                    title={`Run ${collector.display_name}`}
                    style={{ background: 'transparent', border: '1px solid var(--color-border)',
                      borderRadius: 6, padding: '3px 8px', cursor: 'pointer',
                      color: 'var(--color-text)', display: 'flex', alignItems: 'center', gap: 4, fontSize: 11 }}
                  >
                    <Play size={11} /> Run
                  </button>
                </div>
                <div style={{ fontSize: 11, color: 'var(--color-text-muted)', lineHeight: 1.5 }}>{collector.description}</div>
                <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
                  {collector.provider} · {collector.last_status || 'never run'}
                  {collector.last_run ? ` · ${new Date(collector.last_run).toLocaleString()}` : ''}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{ ...card, padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '14px 18px', fontSize: 14, fontWeight: 600 }}>Recent runs</div>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: 'var(--color-surface-2)', borderTop: '1px solid var(--color-border)',
              borderBottom: '1px solid var(--color-border)' }}>
              {['Assessment', 'Trigger', 'Status', 'Started', 'Controls', 'Score'].map((h) => (
                <th key={h} style={{ textAlign: 'left', padding: '9px 14px', fontSize: 12,
                  color: 'var(--color-text-muted)', fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(history || []).map((run) => (
              <tr key={run.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                <td style={{ padding: '9px 14px' }}>{run.assessment_name}</td>
                <td style={{ padding: '9px 14px', textTransform: 'capitalize' }}>{run.trigger}</td>
                <td style={{ padding: '9px 14px', textTransform: 'capitalize' }}>{run.status}</td>
                <td style={{ padding: '9px 14px', color: 'var(--color-text-muted)' }}>
                  {new Date(run.started_at).toLocaleString()}
                </td>
                <td style={{ padding: '9px 14px' }}>{run.total_controls_checked}</td>
                <td style={{ padding: '9px 14px' }}>{run.security_score != null ? `${run.security_score}%` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {(history || []).length === 0 && (
          <div style={{ padding: 28, textAlign: 'center', fontSize: 13, color: 'var(--color-text-muted)' }}>
            No collection runs yet.
          </div>
        )}
      </div>
    </div>
  )
}
