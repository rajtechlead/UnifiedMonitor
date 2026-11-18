import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { api } from './hooks/useApi'
import { useAuthStore } from './store/authStore'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 2,     // 2 minutes
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

/**
 * The Entra callback returns `#access_token=…&refresh_token=…`. Nothing ever
 * read that fragment, so a successful Microsoft sign-in dropped the user back
 * on the login page. Exchange it for the profile once, then clean the URL.
 */
async function consumeSsoFragment(): Promise<void> {
  if (!window.location.hash) return
  const params = new URLSearchParams(window.location.hash.slice(1))
  const accessToken = params.get('access_token')
  const refreshToken = params.get('refresh_token')
  if (!accessToken) return

  window.history.replaceState({}, '', window.location.pathname + window.location.search)
  useAuthStore.getState().setAuth(accessToken, {
    id: '',
    email: '',
    fullName: '',
    role: 'viewer',
    tenantId: '',
  })

  try {
    const me = await api.get('/auth/me')
    useAuthStore.getState().setAuth(accessToken, {
      id: me.data.id,
      email: me.data.email,
      fullName: me.data.display_name,
      role: me.data.role,
      tenantId: me.data.tenant_id || '',
    })
    if (refreshToken) {
      localStorage.setItem('unimonitor-refresh-token', refreshToken)
    }
  } catch {
    useAuthStore.getState().logout()
  }
}

void consumeSsoFragment().finally(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </React.StrictMode>,
  )
})
