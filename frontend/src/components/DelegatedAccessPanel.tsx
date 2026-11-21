import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Building2, Plus, Trash2 } from 'lucide-react'
import { api } from '../hooks/useApi'

type Tenant = { id: string; name: string; display_name?: string | null }
type User = { id: string; email: string; full_name?: string }
type Grant = { user_id: string; email: string; full_name?: string; role: string; granted_by?: string | null }

const FIELD_STYLE: React.CSSProperties = {
  padding: '8px 10px', fontSize: 13, border: '1px solid var(--color-border)',
  borderRadius: 7, background: 'var(--color-surface-2)', color: 'var(--color-text)', outline: 'none',
}

export default function DelegatedAccessPanel() {
  const queryClient = useQueryClient()
  const [tenantId, setTenantId] = useState('')
  const [userId, setUserId] = useState('')
  const [role, setRole] = useState('viewer')
  const [message, setMessage] = useState('')

  const { data: tenants } = useQuery<{ items: Tenant[] }>({
    queryKey: ['tenants', 'delegation'],
    queryFn: () => api.get('/tenants', { params: { page_size: 200 } }).then((response) => response.data),
  })
  const { data: users } = useQuery<{ items: User[] }>({
    queryKey: ['users', 'delegation'],
    queryFn: () => api.get('/users').then((response) => response.data),
  })
  const { data: grants } = useQuery<Grant[]>({
    queryKey: ['tenant-access', tenantId],
    queryFn: () => api.get(`/tenants/${tenantId}/access`).then((response) => response.data),
    enabled: Boolean(tenantId),
  })

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['tenant-access', tenantId] })
  }

  const grant = useMutation({
    mutationFn: () => api.post(`/tenants/${tenantId}/access`, { user_id: userId, role }),
    onSuccess: () => {
      setMessage('Access granted.')
      setUserId('')
      invalidate()
    },
    onError: (error: unknown) => {
      const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setMessage(typeof detail === 'string' ? detail : 'Could not grant access.')
    },
  })

  const revoke = useMutation({
    mutationFn: (id: string) => api.delete(`/tenants/${tenantId}/access/${id}`),
    onSuccess: () => {
      setMessage('Access revoked.')
      invalidate()
    },
    onError: () => setMessage('Could not revoke access.'),
  })

  return (
    <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 12, padding: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
        <Building2 size={18} color="var(--color-brand)" />
        <span style={{ fontSize: 15, fontWeight: 600 }}>Delegated tenant access</span>
      </div>
      <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 16 }}>
        Give an operator a role on one client tenant without changing their home tenant or global role.
      </p>

      <select value={tenantId} onChange={(event) => setTenantId(event.target.value)} style={{ ...FIELD_STYLE, minWidth: 260 }}>
        <option value="">Select a tenant…</option>
        {(tenants?.items || []).map((tenant) => (
          <option key={tenant.id} value={tenant.id}>{tenant.display_name || tenant.name}</option>
        ))}
      </select>

      {tenantId && (
        <>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 14 }}>
            <select value={userId} onChange={(event) => setUserId(event.target.value)} style={{ ...FIELD_STYLE, minWidth: 240 }}>
              <option value="">Select a user…</option>
              {(users?.items || []).map((user) => (
                <option key={user.id} value={user.id}>{user.full_name ? `${user.full_name} (${user.email})` : user.email}</option>
              ))}
            </select>
            <select value={role} onChange={(event) => setRole(event.target.value)} style={FIELD_STYLE}>
              <option value="viewer">Viewer</option>
              <option value="analyst">Analyst</option>
              <option value="auditor">Auditor</option>
            </select>
            <button
              onClick={() => grant.mutate()}
              disabled={!userId || grant.isPending}
              style={{
                padding: '8px 14px', fontSize: 13, background: 'var(--color-brand)', color: 'white',
                border: 'none', borderRadius: 8, cursor: !userId ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', gap: 6, opacity: userId ? 1 : 0.6,
              }}
            >
              <Plus size={14} /> Grant
            </button>
          </div>

          <div style={{ marginTop: 18 }}>
            {(grants || []).length === 0 ? (
              <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>No delegated grants on this tenant.</div>
            ) : (
              (grants || []).map((row) => (
                <div key={row.user_id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '9px 0', borderTop: '1px solid var(--color-border)', fontSize: 13 }}>
                  <span>{row.full_name ? `${row.full_name} (${row.email})` : row.email} · {row.role}</span>
                  <button
                    onClick={() => revoke.mutate(row.user_id)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-danger, #DC2626)' }}
                    aria-label={`Revoke ${row.email}`}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))
            )}
          </div>
        </>
      )}

      {message && <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 12 }}>{message}</div>}
    </div>
  )
}
