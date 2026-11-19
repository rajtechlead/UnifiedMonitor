import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { alertsApi } from '../hooks/useApi'

type Alert = {
  id: string
  title: string
  detail: string | null
  severity: string
  status: string
  metric: string | null
  metric_value: number | null
  threshold: number | null
  triggered_at: string
  notes: string | null
}

type AlertSummary = {
  open: number
  acknowledged: number
  snoozed: number
  resolved: number
  total: number
}

type Policy = {
  id: string
  name: string
  description: string | null
  kind: string
  metric: string
  comparator: string
  threshold: number
  window_hours: number
  severity: string
  enabled: boolean
  notify: boolean
}

type Template = { key: string; name: string; description: string; metric_label: string }

const STATUS = ['', 'open', 'acknowledged', 'snoozed', 'resolved']

const ACTION_LABELS: Record<string, string> = { acknowledged: 'Ack', snoozed: 'Snooze', resolved: 'Resolve' }

const card = {
  background: 'var(--color-surface)',
  border: '1px solid var(--color-border)',
  borderRadius: 12,
  padding: 18,
}

export default function AlertsPage() {
  const [statusFilter, setStatusFilter] = useState('open')
  const [templateKey, setTemplateKey] = useState('')
  const [busy, setBusy] = useState(false)
  const queryClient = useQueryClient()

  const { data: summary } = useQuery<AlertSummary>({
    queryKey: ['alerts', 'summary'],
    queryFn: alertsApi.summary,
  })
  const { data: page, isLoading } = useQuery<{ items: Alert[]; total: number }>({
    queryKey: ['alerts', statusFilter],
    queryFn: () => alertsApi.list({ status: statusFilter || undefined }),
  })
  const { data: policies } = useQuery<Policy[]>({
    queryKey: ['alerts', 'policies'],
    queryFn: alertsApi.policies,
  })
  const { data: templates } = useQuery<Template[]>({
    queryKey: ['alerts', 'templates'],
    queryFn: alertsApi.templates,
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['alerts'] })
  }

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true)
    try {
      await action()
      refresh()
    } finally {
      setBusy(false)
    }
  }

  const alerts = page?.items ?? []

  let listPlaceholder = ''
  if (isLoading) listPlaceholder = 'Loading alerts…'
  else if (alerts.length === 0) listPlaceholder = 'No alerts match this filter.'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Alert Center</h1>
          <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
            Policies watch findings and score history; triggered alerts are triaged here.
          </p>
        </div>
        <button
          onClick={() => run(() => alertsApi.evaluate())}
          disabled={busy}
          style={{ padding: '8px 14px', fontSize: 13, borderRadius: 8, border: '1px solid var(--color-border)',
            background: 'var(--color-surface-2)', color: 'var(--color-text)', cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <RefreshCw size={14} /> Evaluate now
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 14 }}>
        {[
          { label: 'Open', value: summary?.open ?? 0, colour: '#EF4444' },
          { label: 'Acknowledged', value: summary?.acknowledged ?? 0, colour: '#F59E0B' },
          { label: 'Snoozed', value: summary?.snoozed ?? 0, colour: '#64748B' },
          { label: 'Resolved', value: summary?.resolved ?? 0, colour: '#10B981' },
        ].map((item) => (
          <div key={item.label} style={{ ...card, textAlign: 'center' }}>
            <div style={{ fontSize: 26, fontWeight: 700, color: item.colour }}>{item.value}</div>
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 4 }}>{item.label}</div>
          </div>
        ))}
      </div>

      {/* Policies */}
      <div style={card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <div style={{ fontSize: 14, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Bell size={15} color="var(--color-brand)" /> Alert policies
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <select
              value={templateKey}
              onChange={(e) => setTemplateKey(e.target.value)}
              style={{ padding: '6px 10px', fontSize: 12, borderRadius: 6,
                border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
                color: 'var(--color-text)' }}
            >
              <option value="">Add from template…</option>
              {(templates || []).map((t) => (
                <option key={t.key} value={t.key}>{t.name}</option>
              ))}
            </select>
            <button
              disabled={!templateKey || busy}
              onClick={() => run(async () => {
                await alertsApi.fromTemplate(templateKey)
                setTemplateKey('')
              })}
              style={{ padding: '6px 12px', fontSize: 12, borderRadius: 6, border: 'none',
                background: 'var(--color-brand)', color: 'white',
                cursor: templateKey ? 'pointer' : 'not-allowed', opacity: templateKey ? 1 : 0.5,
                display: 'flex', alignItems: 'center', gap: 4 }}
            >
              <Plus size={13} /> Add
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 14 }}>
          {(policies || []).length === 0 && (
            <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
              No policies yet — add one from the templates to start alerting.
            </div>
          )}
          {(policies || []).map((policy) => (
            <div key={policy.id} style={{ display: 'grid', gridTemplateColumns: '1fr 220px 90px 34px',
              gap: 10, alignItems: 'center', fontSize: 12, padding: '8px 10px',
              border: '1px solid var(--color-border)', borderRadius: 8 }}>
              <span>{policy.name}</span>
              <span style={{ color: 'var(--color-text-muted)' }}>
                {policy.metric} {policy.comparator} {policy.threshold} / {policy.window_hours}h
              </span>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={policy.enabled}
                  onChange={(e) => run(() => alertsApi.updatePolicy(policy.id, {
                    name: policy.name, description: policy.description, kind: policy.kind,
                    metric: policy.metric, comparator: policy.comparator,
                    threshold: policy.threshold, window_hours: policy.window_hours,
                    severity: policy.severity, enabled: e.target.checked, notify: policy.notify,
                  }))}
                />
                <span style={{ fontSize: 12 }}>enabled</span>
              </label>
              <button
                onClick={() => run(() => alertsApi.deletePolicy(policy.id))}
                title="Delete policy"
                style={{ background: 'transparent', border: 'none', cursor: 'pointer',
                  color: 'var(--color-text-muted)' }}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Alerts */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          style={{ padding: '6px 10px', fontSize: 13, borderRadius: 6,
            border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
            color: 'var(--color-text)' }}
        >
          {STATUS.map((s) => (
            <option key={s} value={s}>{s || 'All statuses'}</option>
          ))}
        </select>
        <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{page?.total ?? 0} alerts</span>
      </div>

      <div style={{ ...card, padding: 0, overflow: 'hidden' }}>
        {listPlaceholder ? (
          <div style={{ padding: 32, textAlign: 'center', fontSize: 13, color: 'var(--color-text-muted)' }}>{listPlaceholder}</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: 'var(--color-surface-2)', borderBottom: '1px solid var(--color-border)' }}>
                {['Alert', 'Severity', 'Value', 'Triggered', 'Status', 'Actions'].map((h) => (
                  <th key={h} style={{ textAlign: 'left', padding: '10px 14px', fontSize: 12,
                    color: 'var(--color-text-muted)', fontWeight: 600 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {alerts.map((alert) => (
                <tr key={alert.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '10px 14px' }}>
                    <div style={{ fontWeight: 600 }}>{alert.title}</div>
                    {alert.detail && <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{alert.detail}</div>}
                  </td>
                  <td style={{ padding: '10px 14px' }}>
                    <span className={`severity-chip severity-${alert.severity?.toLowerCase()}`}>{alert.severity}</span>
                  </td>
                  <td style={{ padding: '10px 14px', color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
                    {alert.metric_value ?? '—'} / {alert.threshold ?? '—'}
                  </td>
                  <td style={{ padding: '10px 14px', color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
                    {new Date(alert.triggered_at).toLocaleString()}
                  </td>
                  <td style={{ padding: '10px 14px', textTransform: 'capitalize' }}>{alert.status}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      {['acknowledged', 'snoozed', 'resolved'].map((next) => (
                        <button
                          key={next}
                          disabled={busy || alert.status === next}
                          onClick={() => run(() => alertsApi.updateStatus(alert.id, { status: next, snooze_hours: 24 }))}
                          style={{ padding: '3px 8px', fontSize: 11, borderRadius: 5, cursor: 'pointer',
                            border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
                            color: 'var(--color-text)', opacity: alert.status === next ? 0.4 : 1 }}
                        >
                          {ACTION_LABELS[next] ?? next}
                        </button>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
