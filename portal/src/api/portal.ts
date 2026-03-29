import client from './client'
import type { Plan, PlanDetail, PlanStep, HREmployee, HRLeaveApplication } from '../types'

export async function getPlans(userId?: string, status?: string, limit = 20): Promise<Plan[]> {
  const params: Record<string, unknown> = { limit }
  if (userId) params.user_id = userId
  if (status) params.status = status
  const res = await client.get('/api/plans', { params })
  return res.data.plans ?? []
}

export async function getPlanDetail(planId: string): Promise<PlanDetail> {
  const res = await client.get(`/api/plans/${planId}`)
  return res.data
}

export async function getPlanStep(planId: string, stepId: string): Promise<PlanStep> {
  const res = await client.get(`/api/plans/${planId}/steps/${stepId}`)
  return res.data
}

export async function killPlan(planId: string): Promise<{ status: string; plan_id: string; steps_cancelled: number }> {
  const res = await client.post(`/api/plans/${planId}/kill`)
  return res.data
}

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
  getTaskStats: () => client.get('/api/admin-portal/tasks/stats'),
  deleteTask: (taskId: string) => client.delete(`/api/admin-portal/tasks/${taskId}`),
  getScheduledTasksAdmin: () => client.get('/api/admin-portal/tasks/scheduled'),
  runScheduledTask: (jobId: string) => client.post(`/api/admin-portal/tasks/scheduled/${jobId}/run`),
  pauseScheduledTask: (jobId: string) => client.post(`/api/admin-portal/tasks/scheduled/${jobId}/pause`),
  resumeScheduledTask: (jobId: string) => client.post(`/api/admin-portal/tasks/scheduled/${jobId}/resume`),

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

  sendAgentMessage: (dept: string, message: string, sessionId: string) =>
    client.post('/chat/send', {
      message,
      department: dept,
      session_id: sessionId,
    }),
  getActiveTasks: (sessionId: string) =>
    client.get('/tasks/active', { params: { session_id: sessionId } }),
  getTaskById: (taskId: string) => client.get(`/tasks/${taskId}`),
  downloadFile: async (id: string, filename: string): Promise<void> => {
    const response = await client.get(`/api/admin-portal/files/${id}/download`, {
      responseType: 'blob',
    })
    const url = URL.createObjectURL(response.data)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  },

  // CRM
  getCrmLeads: (page = 1, status?: string, search?: string, country?: string) =>
    client.get('/api/admin-portal/crm/leads', { params: { page, per_page: 20, ...(status ? { status } : {}), ...(search ? { search } : {}), ...(country ? { country } : {}) } }),
  getCrmPipeline: () => client.get('/api/admin-portal/crm/pipeline'),
  getCrmCountries: () => client.get('/api/admin-portal/crm/countries'),
  createLead: (data: Record<string, unknown>) => client.post('/api/admin-portal/crm/leads', data),
  updateLead: (id: string, data: Record<string, unknown>) => client.patch(`/api/admin-portal/crm/leads/${id}`, data),
  getCrmLeadDetail: (id: string) =>
    client.get(`/api/admin-portal/crm/leads/${id}`),
  getCrmLeadActivities: (id: string) =>
    client.get(`/api/admin-portal/crm/leads/${id}/activities`),
  addLeadActivity: (id: string, data: { type: string; title: string; body?: string }) =>
    client.post(`/api/admin-portal/crm/leads/${id}/activities`, data),

  // Users
  getUsers: () => client.get('/api/admin-portal/users'),
  getUser: (id: string) => client.get(`/api/admin-portal/users/${id}`),
  createUser: (data: { email: string; name: string; department: string; role: string }) =>
    client.post('/api/admin-portal/users', data),
  updateUser: (id: string, data: Partial<{ name: string; department: string; role: string; is_active: boolean }>) =>
    client.patch(`/api/admin-portal/users/${id}`, data),
  deleteUser: (id: string) => client.delete(`/api/admin-portal/users/${id}`),

  // HR — Employees
  getHREmployees: (params?: { department?: string; country?: string; is_active?: boolean; search?: string }) =>
    client.get('/api/admin-portal/hr/employees', { params }),
  createHREmployee: (data: Partial<HREmployee>) =>
    client.post('/api/admin-portal/hr/employees', data),
  getHREmployee: (id: string) =>
    client.get(`/api/admin-portal/hr/employees/${id}`),
  updateHREmployee: (id: string, data: Partial<HREmployee>) =>
    client.put(`/api/admin-portal/hr/employees/${id}`, data),
  patchHREmployeeStatus: (id: string, is_active: boolean) =>
    client.patch(`/api/admin-portal/hr/employees/${id}/status`, { is_active }),
  getHREmployeeProfile: (id: string) =>
    client.get(`/api/admin-portal/hr/employees/${id}/profile`),
  getHRLeaveBalance: (id: string, year?: number) =>
    client.get(`/api/admin-portal/hr/employees/${id}/leave-balance`, { params: { year } }),

  // HR — Leave
  applyLeave: (data: Partial<HRLeaveApplication>) =>
    client.post('/api/admin-portal/hr/leave/apply', data),
  getLeaveApplications: (params?: { employee_id?: string; status?: string; year?: number }) =>
    client.get('/api/admin-portal/hr/leave/applications', { params }),
  getMyLeaveApplications: () =>
    client.get('/api/admin-portal/hr/leave/applications'),
  updateLeaveStatus: (id: string, status: string, comment?: string) =>
    client.patch(`/api/admin-portal/hr/leave/applications/${id}/status`, { status, comment }),
  getPendingApprovals: () =>
    client.get('/api/admin-portal/hr/leave/pending-approvals'),
  getLeaveTypes: (country?: string) =>
    client.get('/api/admin-portal/hr/leave/types', { params: { country } }),

  // HR — Dashboard
  getHRLeaveDashboard: (params?: { year?: number; department?: string; country?: string }) =>
    client.get('/api/admin-portal/hr/dashboard/leave-summary', { params }),
}
