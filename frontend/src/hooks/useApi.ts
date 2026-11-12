import axios from 'axios'
import { useAuthStore } from '../store/authStore'

export const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Auto-logout on 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// ── API functions ────────────────────────────────────────────────────────────

export const dashboardApi = {
  getExecutive: () => api.get('/dashboard/executive').then((r) => r.data),
  getSecurity: () => api.get('/dashboard/security').then((r) => r.data),
  getCompliance: () => api.get('/dashboard/compliance').then((r) => r.data),
  getRisk: () => api.get('/dashboard/risk').then((r) => r.data),
}

export const findingsApi = {
  list: (params?: Record<string, unknown>) =>
    api.get('/findings', { params }).then((r) => r.data),
  get: (id: string) => api.get(`/findings/${id}`).then((r) => r.data),
  update: (id: string, data: Record<string, unknown>) =>
    api.patch(`/findings/${id}`, data).then((r) => r.data),
  getRemediation: (id: string) =>
    api.get(`/findings/${id}/remediation`).then((r) => r.data),
}

export const assessmentsApi = {
  list: () => api.get('/assessments').then((r) => r.data),
  create: (data: Record<string, unknown>) =>
    api.post('/assessments', data).then((r) => r.data),
  run: (id: string) => api.post(`/assessments/${id}/run`).then((r) => r.data),
  getRuns: (id: string) =>
    api.get(`/assessments/${id}/runs`).then((r) => r.data),
}

export const reportsApi = {
  list: (tenantId?: string) =>
    api.get('/reports', { params: tenantId ? { tenant_id: tenantId } : {} }).then((r) => r.data),
  listRuns: (tenantId?: string, page = 1, pageSize = 20) =>
    api
      .get('/reports/runs', { params: { page, page_size: pageSize, ...(tenantId ? { tenant_id: tenantId } : {}) } })
      .then((r) => r.data),
  generate: (runId: string, formats: string[]) =>
    api.post('/reports/generate', { run_id: runId, formats }).then((r) => r.data),
  download: (id: string, format: string) =>
    api.get(`/reports/${id}/download/${format}`, { responseType: 'blob' }),
}

export const monitoringApi = {
  health: () => api.get('/monitoring/health').then((r) => r.data),
  collectors: () => api.get('/monitoring/collectors').then((r) => r.data),
  runCollector: (name: string) =>
    api.post(`/monitoring/collectors/${name}/run`).then((r) => r.data),
}
