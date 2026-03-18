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
  updateJob: (jobId: string, data: Record<string, unknown>) =>
    client.put(`/api/admin-portal/scheduler/jobs/${jobId}`, data),

  // Agents
  getAgents: () => client.get('/api/admin-portal/agents'),
  getAgentMemory: (agent: string) => client.get(`/api/admin-portal/agents/${agent}/rag-memory`),

  // RAG memory
  uploadAgentMemory: (agent: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return client.post(`/api/admin-portal/agents/${agent}/rag-memory/upload`, form, {
      headers: { 'Content-Type': undefined },
    })
  },
  deleteAgentMemory: (agent: string, filename: string) =>
    client.delete(`/api/admin-portal/agents/${agent}/rag-memory/${encodeURIComponent(filename)}`),

  // Tasks
  getTasks: (page = 1, status?: string) =>
    client.get('/api/admin-portal/tasks', { params: { page, per_page: 20, ...(status ? { status } : {}) } }),
  killTask: (taskId: string) =>
    client.post(`/api/admin-portal/tasks/${taskId}/kill`),

  // Files
  getFiles: (params?: { user_id?: string; type?: string; page?: number }) =>
    client.get('/api/admin-portal/files', { params }),
  getFolderTree: () => client.get('/api/admin-portal/files/folder-tree'),
  renameFile: (id: string, newFilename: string) =>
    client.patch(`/api/admin-portal/files/${id}/rename`, { new_filename: newFilename }),
  uploadFile: (file: File, department?: string, scope?: string) => {
    const form = new FormData()
    form.append('file', file)
    if (department) form.append('department', department)
    form.append('scope', scope || 'shared')
    return client.post('/api/admin-portal/files/upload', form, {
      headers: { 'Content-Type': undefined },
    })
  },
  deleteFile: (id: string) => client.delete(`/api/admin-portal/files/${id}`),

  // CRM
  getCrmLeads: (page = 1, status?: string, search?: string) =>
    client.get('/api/admin-portal/crm/leads', { params: { page, per_page: 20, ...(status ? { status } : {}), ...(search ? { search } : {}) } }),
  getCrmPipeline: () => client.get('/api/admin-portal/crm/pipeline'),

  // Users
  getUsers: () => client.get('/api/admin-portal/users'),
  getUser: (id: string) => client.get(`/api/admin-portal/users/${id}`),
  createUser: (data: { email: string; name: string; department: string; role: string }) =>
    client.post('/api/admin-portal/users', data),
  updateUser: (id: string, data: Partial<{ name: string; department: string; role: string; is_active: boolean }>) =>
    client.patch(`/api/admin-portal/users/${id}`, data),
  deleteUser: (id: string) => client.delete(`/api/admin-portal/users/${id}`),
}
