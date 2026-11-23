import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, CheckCircle, XCircle } from 'lucide-react'
import { aiApi, errorDetail } from '../hooks/useApi'

const MASK = '******'

const input: React.CSSProperties = {
  padding: '6px 8px', fontSize: 12, borderRadius: 6, width: '100%', boxSizing: 'border-box',
  border: '1px solid var(--color-border)', background: 'var(--color-surface-2)', color: 'var(--color-text)',
}

type Draft = { model: string; api_key: string; enabled: boolean }

/**
 * Built-in AI providers with the tenant's own keys and an explicit failover order.
 *
 * The API never returns a key: a stored one comes back as `******`, and sending that
 * mask back keeps it. The order here is the auto-switchover sequence the remediation
 * chain follows when a provider is out of quota or unavailable.
 */
export default function BuiltinAiProviders() {
  const qc = useQueryClient()
  const { data, isError, error } = useQuery({ queryKey: ['ai-settings'], queryFn: aiApi.settings })
  const [drafts, setDrafts] = useState<Record<string, Draft>>({})
  const [order, setOrder] = useState<string[]>([])
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!data) return
    setDrafts(Object.fromEntries(data.providers.map(provider => [
      provider.name,
      { model: provider.model, api_key: provider.key_hint || '', enabled: provider.enabled },
    ])))
    setOrder(data.order.length ? data.order : data.providers.map(provider => provider.name))
  }, [data])

  const save = useMutation({
    mutationFn: () => aiApi.saveSettings(
      order.map(name => ({
        name,
        model: drafts[name]?.model || '',
        enabled: drafts[name]?.enabled ?? true,
        api_key: drafts[name]?.api_key || MASK,
      })),
      order,
    ),
    onSuccess: () => {
      setMessage('Provider sequence saved.')
      void qc.invalidateQueries({ queryKey: ['ai-settings'] })
      void qc.invalidateQueries({ queryKey: ['ai-status'] })
    },
    onError: (err) => setMessage(errorDetail(err, 'Could not save the provider sequence.')),
  })

  const test = useMutation({
    mutationFn: (name: string) => aiApi.testProvider(name),
    onSuccess: (result) => setMessage(result.ok
      ? `${result.name} answered successfully${result.model ? ` (${result.model})` : ''}.`
      : `${result.name} failed: ${result.error || 'no answer'}.`),
    onError: (err) => setMessage(errorDetail(err, 'The provider test could not run.')),
  })

  const move = (name: string, delta: number) => {
    setOrder(previous => {
      const next = [...previous]
      const index = next.indexOf(name)
      const target = index + delta
      if (index < 0 || target < 0 || target >= next.length) return previous
      next.splice(index, 1)
      next.splice(target, 0, name)
      return next
    })
  }

  if (isError) {
    return <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{errorDetail(error, 'AI settings are unavailable.')}</div>
  }

  const providers = data?.providers || []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 18 }}>
      <div style={{ fontSize: 13, fontWeight: 600 }}>Built-in providers and auto-switchover</div>
      <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
        Add your own key for any built-in provider, then order them. The first provider that answers is used;
        an exhausted, rate-limited or unavailable one is skipped automatically. A key stays in the vault and
        is shown only as a mask.
      </div>

      {providers.map(provider => {
        const draft = drafts[provider.name] || { model: provider.model, api_key: '', enabled: provider.enabled }
        return (
          <div key={provider.name} style={{
            border: '1px solid var(--color-border)', borderRadius: 8, padding: 10,
            display: 'grid', gridTemplateColumns: '1.2fr 1.4fr 1.2fr auto auto auto', gap: 8, alignItems: 'center',
          }}>
            <div>
              <div style={{ fontSize: 12, fontWeight: 600 }}>{provider.label}</div>
              <div style={{ fontSize: 10, color: provider.configured ? '#10B981' : 'var(--color-text-muted)' }}>
                {provider.configured ? 'configured' : 'not connected'}{provider.free_tier ? ' · free tier' : ''}
              </div>
            </div>
            <input
              aria-label={`${provider.name} model`}
              style={input}
              value={draft.model}
              onChange={e => setDrafts(prev => ({ ...prev, [provider.name]: { ...draft, model: e.target.value } }))}
              placeholder={provider.default_model}
            />
            <input
              aria-label={`${provider.name} API key`}
              type="password"
              style={input}
              value={draft.api_key}
              onChange={e => setDrafts(prev => ({ ...prev, [provider.name]: { ...draft, api_key: e.target.value } }))}
              placeholder="API key"
            />
            <label style={{ fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}>
              <input
                type="checkbox"
                checked={draft.enabled}
                onChange={e => setDrafts(prev => ({ ...prev, [provider.name]: { ...draft, enabled: e.target.checked } }))}
              />
              on
            </label>
            <div style={{ display: 'flex', gap: 2 }}>
              <button type="button" aria-label={`Move ${provider.name} earlier`} onClick={() => move(provider.name, -1)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)' }}>
                <ArrowUp size={13} />
              </button>
              <button type="button" aria-label={`Move ${provider.name} later`} onClick={() => move(provider.name, 1)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)' }}>
                <ArrowDown size={13} />
              </button>
            </div>
            <button
              type="button"
              onClick={() => test.mutate(provider.name)}
              disabled={test.isPending}
              style={{ padding: '4px 8px', fontSize: 11, borderRadius: 6, border: '1px solid var(--color-border)', background: 'transparent', color: 'var(--color-text)', cursor: 'pointer' }}
            >
              Test
            </button>
          </div>
        )
      })}

      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          type="button"
          onClick={() => save.mutate()}
          disabled={save.isPending || providers.length === 0}
          style={{
            padding: '7px 14px', fontSize: 12, background: 'var(--color-brand)', color: 'white',
            border: 'none', borderRadius: 6, cursor: save.isPending ? 'not-allowed' : 'pointer',
          }}
        >
          {save.isPending ? 'Saving…' : 'Save sequence'}
        </button>
        {order.length > 0 && (
          <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>Order: {order.join(' → ')}</span>
        )}
        {message && (
          <span style={{ fontSize: 11, color: message.toLowerCase().includes('fail') ? '#EF4444' : '#10B981', display: 'flex', alignItems: 'center', gap: 4 }}>
            {message.toLowerCase().includes('fail') ? <XCircle size={12} /> : <CheckCircle size={12} />}
            {message}
          </span>
        )}
      </div>
    </div>
  )
}
