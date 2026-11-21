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

/** Read the API's ``detail`` string, falling back to a caller-supplied message. */
export function errorDetail(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

// ── API functions ────────────────────────────────────────────────────────────

export const healthApi = {
  // Unauthenticated: the build's own version, so the UI never hardcodes one.
  get: () => api.get('/health').then((r) => r.data as { status: string; version: string }),
}

export const dashboardApi = {
  getExecutive: () => api.get('/dashboard/executive').then((r) => r.data),
  getSecurity: () => api.get('/dashboard/security').then((r) => r.data),
  getCompliance: () => api.get('/dashboard/compliance').then((r) => r.data),
  getRisk: () => api.get('/dashboard/risk').then((r) => r.data),
  getSoc: () => api.get('/dashboard/soc').then((r) => r.data),
  getAudit: () => api.get('/dashboard/audit').then((r) => r.data),
  getClouds: () => api.get('/dashboard/clouds').then((r) => r.data),
  getCiso: () => api.get('/dashboard/ciso').then((r) => r.data),
  getZeroTrust: () => api.get('/dashboard/zero-trust').then((r) => r.data),
  getAuditVerify: () => api.get('/dashboard/audit/verify').then((r) => r.data),
  getCloudProvider: (providerId: string) =>
    api.get(`/dashboard/clouds/${providerId}`).then((r) => r.data),
}

export const zerotrustApi = {
  summary: () => api.get('/zerotrust/summary').then((r) => r.data),
  checks: (params?: Record<string, unknown>) =>
    api.get('/zerotrust/checks', { params }).then((r) => r.data),
  runs: () => api.get('/zerotrust/runs').then((r) => r.data),
  importReport: (payload: unknown) =>
    api.post('/zerotrust/import', { source: 'microsoft', payload }).then((r) => r.data),
  evaluate: (platform: string) =>
    api.post('/zerotrust/run', { platform }).then((r) => r.data),
  evaluateAll: () => api.post('/zerotrust/run-all').then((r) => r.data),
  mapping: (source: string) => api.get('/zerotrust/mapping', { params: { source } }).then((r) => r.data),
  evidenceGaps: (source: string) => api.get('/zerotrust/evidence-gaps', { params: { source } }).then((r) => r.data),
  script: () => api.get('/zerotrust/script', { responseType: 'text' }).then((r) => r.data),
}

export const grcApi = {
  frameworks: () => api.get('/grc/frameworks').then((r) => r.data),
  frameworkControls: (frameworkId: string, tenantId?: string) =>
    api
      .get(`/grc/frameworks/${frameworkId}/controls`, { params: tenantId ? { tenant_id: tenantId } : {} })
      .then((r) => r.data),
}

export const usersApi = {
  list: () => api.get('/users').then((r) => r.data),
  create: (data: Record<string, unknown>) => api.post('/users', data).then((r) => r.data),
  setRole: (id: string, role: string) => api.put(`/users/${id}/role`, { role }).then((r) => r.data),
  setActive: (id: string, is_active: boolean) => api.put(`/users/${id}`, { is_active }).then((r) => r.data),
  remove: (id: string) => api.delete(`/users/${id}`),
}

export const findingsApi = {
  list: (params?: Record<string, unknown>) =>
    api.get('/findings', { params }).then((r) => r.data),
  get: (id: string) => api.get(`/findings/${id}`).then((r) => r.data),
  // The API calls a compliance state change `/state`; PATCH /findings/{id} does not exist.
  updateState: (id: string, state: string, comment?: string) =>
    api.patch(`/findings/${id}/state`, { state, comment }).then((r) => r.data),
  triage: (id: string, data: Record<string, unknown>) =>
    api.post(`/findings/${id}/triage`, data).then((r) => r.data),
  history: (id: string) => api.get(`/findings/${id}/history`).then((r) => r.data),
  timeline: (id: string) => api.get(`/findings/${id}/timeline`).then((r) => r.data),
  summary: (tenantId?: string) =>
    api.get('/findings/summary', { params: tenantId ? { tenant_id: tenantId } : {} }).then((r) => r.data),
  priority: (tenantId?: string) =>
    api.get('/findings/priority', { params: tenantId ? { tenant_id: tenantId } : {} }).then((r) => r.data),
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
  schedule: () => api.get('/monitoring/schedule').then((r) => r.data),
  collect: () => api.post('/monitoring/collect').then((r) => r.data),
  history: () => api.get('/monitoring/collection-history').then((r) => r.data),
  licensing: () => api.get('/monitoring/licensing').then((r) => r.data),
  serviceHealth: () => api.get('/monitoring/service-health').then((r) => r.data),
}

export const alertsApi = {
  summary: () => api.get('/alerts/summary').then((r) => r.data),
  list: (params?: Record<string, unknown>) => api.get('/alerts', { params }).then((r) => r.data),
  policies: () => api.get('/alerts/policies').then((r) => r.data),
  templates: () => api.get('/alerts/templates').then((r) => r.data),
  createPolicy: (data: Record<string, unknown>) => api.post('/alerts/policies', data).then((r) => r.data),
  fromTemplate: (templateKey: string) =>
    api.post('/alerts/policies/from-template', { template_key: templateKey }).then((r) => r.data),
  updatePolicy: (id: string, data: Record<string, unknown>) =>
    api.put(`/alerts/policies/${id}`, data).then((r) => r.data),
  deletePolicy: (id: string) => api.delete(`/alerts/policies/${id}`).then((r) => r.data),
  evaluate: () => api.post('/alerts/evaluate').then((r) => r.data),
  updateStatus: (id: string, data: Record<string, unknown>) =>
    api.post(`/alerts/${id}/status`, data).then((r) => r.data),
}

export const searchApi = {
  search: (q: string) => api.get('/search', { params: { q } }).then((r) => r.data),
}
