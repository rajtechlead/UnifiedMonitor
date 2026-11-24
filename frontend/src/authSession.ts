import { api } from './hooks/useApi'
import { useAuthStore } from './store/authStore'

export type SessionUser = {
  id: string
  email: string
  fullName: string
  role: string
  tenantId: string
}

type Profile = {
  id: string
  email: string
  display_name: string
  role: string
  tenant_id: string | null
}

export function userFromProfile(profile: Profile): SessionUser {
  return {
    id: profile.id,
    email: profile.email,
    fullName: profile.display_name,
    role: profile.role,
    tenantId: profile.tenant_id ?? '',
  }
}

/**
 * Store a token and read back the real account.
 *
 * The login response now carries the profile, but an SSO redirect only carries the
 * token, and a stale persisted role would otherwise show an administrator as a
 * viewer until the next reload.
 */
export async function establishSession(accessToken: string, profile?: Profile): Promise<void> {
  if (profile) {
    useAuthStore.getState().setAuth(accessToken, userFromProfile(profile))
    return
  }
  // A placeholder lets the request interceptor send the new token; /me replaces it.
  useAuthStore.getState().setAuth(accessToken, {
    id: '', email: '', fullName: '', role: 'viewer', tenantId: '',
  })
  const me = await api.get('/auth/me')
  useAuthStore.getState().setAuth(accessToken, userFromProfile(me.data as Profile))
}

export function accessTokenFromLocationHash(): string | null {
  const raw = window.location.hash.startsWith('#') ? window.location.hash.slice(1) : window.location.hash
  if (!raw) return null
  const token = new URLSearchParams(raw).get('access_token')
  return token || null
}
