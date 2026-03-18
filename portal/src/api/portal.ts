import client from './client'

export const portalApi = {
  // Dashboard
  getSessions: () => client.get('/api/admin-portal/dashboard/sessions'),
  getLlmUsage: (period: 'today' | 'week' | 'month' = 'today') =>
    client.get(`/api/admin-portal/dashboard/llm-usage?period=${period}`),
  getSystemVitals: () => client.get('/api/admin-portal/dashboard/system-vitals'),
  getAgentStatus: () => client.get('/api/admin-portal/dashboard/agent-status'),

  // Scheduler
  getJobs: () => client.get('/api/admin-portal/scheduler/jobs'),
  getJobHistory: (jobId: string) => client.get(`/api/admin-portal/scheduler/jobs/${jobId}/history`),
  triggerJob: (jobId: string) => client.post(`/api/admin-portal/scheduler/jobs/${jobId}/trigger`),
  toggleJob: (jobId: string) => client.patch(`/api/admin-portal/scheduler/jobs/${jobId}/toggle`),

  // Agents
  getAgents: () => client.get('/api/admin-portal/agents'),
  getAgentMemory: (agent: string) => client.get(`/api/admin-portal/agents/${agent}/rag-memory`),

  // Files
  getFiles: (params?: { user_id?: string; type?: string; page?: number }) =>
    client.get('/api/admin-portal/files', { params }),
  deleteFile: (id: string) => client.delete(`/api/admin-portal/files/${id}`),

  // Users
  getUsers: () => client.get('/api/admin-portal/users'),
  getUser: (id: string) => client.get(`/api/admin-portal/users/${id}`),
  createUser: (data: { email: string; name: string; department: string; role: string }) =>
    client.post('/api/admin-portal/users', data),
  updateUser: (id: string, data: Partial<{ name: string; department: string; role: string; is_active: boolean }>) =>
    client.patch(`/api/admin-portal/users/${id}`, data),
  deleteUser: (id: string) => client.delete(`/api/admin-portal/users/${id}`),
}
