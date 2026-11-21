import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { UserPlus, UserX, Users } from 'lucide-react'
import { usersApi } from '../hooks/useApi'
import { useAuthStore } from '../store/authStore'

type ManagedUser = {
  id: string
  email: string
  full_name: string
  role: string
  is_active: boolean
  has_password: boolean
  last_login_at: string | null
  created_at: string
}

const ROLES = ['admin', 'analyst', 'auditor', 'viewer']

const inputStyle: React.CSSProperties = {
  padding: '8px 10px', fontSize: 13, borderRadius: 7,
  border: '1px solid var(--color-border)', background: 'var(--color-surface-2)',
  color: 'var(--color-text)', outline: 'none',
}

export default function UsersPage() {
  const qc = useQueryClient()
  const me = useAuthStore(s => s.user)
  const [showAdd, setShowAdd] = useState(false)
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [role, setRole] = useState('viewer')
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [error, setError] = useState('')

  const { data: users, isLoading, isError, refetch } = useQuery<ManagedUser[]>({
    queryKey: ['users'],
    queryFn: usersApi.list,
  })

  const refresh = () => qc.invalidateQueries({ queryKey: ['users'] })

  const create = useMutation({
    mutationFn: () => usersApi.create({ email: email.trim(), full_name: fullName.trim(), role }),
    onSuccess: () => {
      setEmail(''); setFullName(''); setRole('viewer'); setShowAdd(false); setError('')
      void refresh()
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Could not add this user.')
    },
  })
  const changeRole = useMutation({
    mutationFn: ({ id, value }: { id: string; value: string }) => usersApi.setRole(id, value),
    onSuccess: refresh,
    onError: (err: unknown) => {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Could not change the role.')
    },
  })
  const setActive = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) => usersApi.setActive(id, active),
    onSuccess: refresh,
    onError: (err: unknown) => {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Could not update the user.')
    },
  })
  const remove = useMutation({
    mutationFn: (id: string) => usersApi.remove(id),
    onSuccess: refresh,
    onError: (err: unknown) => {
      setError((err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Could not remove the user.')
    },
  })

  const shown = useMemo(() => {
    const query = search.trim().toLowerCase()
    return (users ?? []).filter(u =>
      (!roleFilter || u.role === roleFilter) &&
      (!query || u.email.toLowerCase().includes(query) || u.full_name.toLowerCase().includes(query))
    )
  }, [users, search, roleFilter])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Users size={18} /> Users &amp; Access
          </h1>
          <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
            Roles are stored in UniMonitor — no Entra ID changes needed.{' '}
            <strong>Admin</strong> = full access · <strong>Analyst</strong> = triage and assessments ·{' '}
            <strong>Auditor</strong> = read-only compliance · <strong>Viewer</strong> = read-only.
          </p>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          style={{
            padding: '8px 14px', fontSize: 13, background: 'var(--color-brand)', color: 'white',
            border: 'none', borderRadius: 8, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
          }}
        >
          <UserPlus size={14} /> {showAdd ? 'Cancel' : 'Add user'}
        </button>
      </div>

      {error && (
        <div style={{
          padding: '10px 12px', borderRadius: 8, fontSize: 13,
          background: 'var(--color-critical-bg)', color: 'var(--color-critical)',
        }}>
          {error}
        </div>
      )}

      {showAdd && (
        <div style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-brand)',
          borderRadius: 12, padding: 16, display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center',
        }}>
          <input style={{ ...inputStyle, flex: 1, minWidth: 220 }} type="email" placeholder="user@domain.com"
            aria-label="Email" value={email} onChange={e => setEmail(e.target.value)} />
          <input style={{ ...inputStyle, flex: 1, minWidth: 180 }} placeholder="Display name"
            aria-label="Display name" value={fullName} onChange={e => setFullName(e.target.value)} />
          <select style={inputStyle} aria-label="Role" value={role} onChange={e => setRole(e.target.value)}>
            {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
          <button
            onClick={() => create.mutate()}
            disabled={create.isPending || !email.includes('@')}
            style={{
              padding: '8px 14px', fontSize: 13, background: 'var(--color-brand)', color: 'white',
              border: 'none', borderRadius: 7, cursor: 'pointer', opacity: email.includes('@') ? 1 : 0.5,
            }}
          >
            {create.isPending ? 'Adding…' : 'Add'}
          </button>
          <div style={{ flexBasis: '100%', fontSize: 11, color: 'var(--color-text-muted)' }}>
            Users sign in with Microsoft. A local password is not required.
          </div>
        </div>
      )}

      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 10, padding: 14, display: 'flex', gap: 10, flexWrap: 'wrap',
      }}>
        <input
          value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Search by name or email…" aria-label="Search users"
          style={{ ...inputStyle, flex: 1, minWidth: 200 }}
        />
        <select value={roleFilter} onChange={e => setRoleFilter(e.target.value)} aria-label="Filter by role" style={inputStyle}>
          <option value="">All roles</option>
          {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
        </select>
      </div>

      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, overflow: 'hidden',
      }}>
        {isLoading && (
          <div style={{ padding: 40, textAlign: 'center', fontSize: 13, color: 'var(--color-text-muted)' }}>Loading users…</div>
        )}
        {!isLoading && isError && (
          <div style={{ padding: 40, textAlign: 'center', fontSize: 13, color: 'var(--color-text-muted)' }}>
            Could not load users. Only an administrator can view this page.{' '}
            <button onClick={() => refetch()} style={{ background: 'none', border: 'none', color: 'var(--color-brand)', cursor: 'pointer' }}>
              Retry
            </button>
          </div>
        )}
        {!isLoading && !isError && shown.length === 0 && (
          <div style={{ padding: 40, textAlign: 'center', fontSize: 13, color: 'var(--color-text-muted)' }}>
            No users match these filters.
          </div>
        )}
        {!isLoading && !isError && shown.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: 'var(--color-surface-2)', borderBottom: '1px solid var(--color-border)' }}>
                {['User', 'Email', 'Role', 'Status', 'Last sign-in', 'Actions'].map(header => (
                  <th key={header} style={{
                    textAlign: 'left', padding: '10px 14px', fontSize: 12, fontWeight: 600,
                    color: 'var(--color-text-muted)',
                  }}>{header}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {shown.map(user => (
                <tr key={user.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '10px 14px' }}>
                    {user.full_name || '—'}
                    {user.id === me?.id && <span style={{ marginLeft: 6, fontSize: 11, color: 'var(--color-text-muted)' }}>(you)</span>}
                  </td>
                  <td style={{ padding: '10px 14px', color: 'var(--color-text-muted)' }}>{user.email}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <select
                      value={user.role}
                      disabled={changeRole.isPending}
                      onChange={e => changeRole.mutate({ id: user.id, value: e.target.value })}
                      aria-label={`Role for ${user.email}`}
                      style={{ ...inputStyle, padding: '3px 8px', fontSize: 12 }}
                    >
                      {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </td>
                  <td style={{ padding: '10px 14px', color: user.is_active ? '#10B981' : '#EF4444' }}>
                    {user.is_active ? 'Active' : 'Disabled'}
                  </td>
                  <td style={{ padding: '10px 14px', color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
                    {user.last_login_at ? new Date(user.last_login_at).toLocaleString() : 'Never'}
                  </td>
                  <td style={{ padding: '10px 14px' }}>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button
                        onClick={() => setActive.mutate({ id: user.id, active: !user.is_active })}
                        style={{
                          padding: '4px 10px', fontSize: 11, background: 'transparent',
                          border: '1px solid var(--color-border)', borderRadius: 5,
                          color: 'var(--color-text-muted)', cursor: 'pointer',
                        }}
                      >
                        {user.is_active ? 'Disable' : 'Enable'}
                      </button>
                      {user.id !== me?.id && (
                        <button
                          onClick={() => {
                            if (window.confirm(`Remove ${user.email}? Their Microsoft 365 account is not affected.`)) {
                              remove.mutate(user.id)
                            }
                          }}
                          style={{
                            padding: '4px 10px', fontSize: 11, background: 'transparent',
                            border: '1px solid #EF4444', borderRadius: 5, color: '#EF4444',
                            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4,
                          }}
                        >
                          <UserX size={11} /> Remove
                        </button>
                      )}
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
