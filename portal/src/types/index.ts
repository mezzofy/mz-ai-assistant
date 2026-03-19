export interface User {
  id: string
  email: string
  name: string
  department: string
  role: string
  is_active: boolean
  last_login_at: string | null
  created_at: string
  session_count?: number
}

export interface Session {
  session_id: string
  user_id: string
  user_name: string
  department: string
  agent: string
  last_active: string | null
  message_count: number
  is_active: boolean
}

export interface LlmModel {
  model: string
  total_tokens: number
  input_tokens: number
  output_tokens: number
  total_cost_usd: number
  request_count: number
  daily_budget_usd: number
  today_cost_usd: number
  budget_pct: number
}

export interface SystemVitals {
  cpu: { percent: number; load_avg_1m: number; load_avg_5m: number; load_avg_15m: number }
  memory: { total_gb: number; used_gb: number; available_gb: number; percent: number }
  disk: { total_gb: number; used_gb: number; free_gb: number; percent: number }
  services: {
    fastapi: boolean
    postgresql: boolean
    redis: boolean
    celery_workers: number
    celery_beat: boolean
  }
}

export interface AgentStatus {
  name: string
  department: string
  is_busy: boolean
  tasks_today: number
  current_task: string | null
}

export interface ScheduledJob {
  id: string
  name: string
  schedule: string
  deliver_to: Record<string, unknown>
  is_active: boolean
  last_run: string | null
  next_run: string | null
  agent: string
  workflow_name: string | null
  user_email: string
  user_name: string
}

export interface FileRecord {
  id: string
  filename: string
  file_type: string
  scope: string
  department: string | null
  owner_email: string | null
  size_bytes: number | null
  created_at: string
  download_url: string
  subfolder?: string | null
}

export interface FolderGroup {
  scope: string
  department: string | null
  owner_email: string | null
  files: FileRecord[]
}

export interface Agent {
  name: string
  department: string
  persona?: string
  description?: string
  skills: string[]
  tools_allowed?: string[]
  llm_model?: string
  is_orchestrator?: boolean
  is_busy: boolean
  tasks_today: number
  rag_memory_count: number
}

export interface AgentTask {
  id: string
  title: string | null
  status: string
  department: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
  error: string | null
  triggered_by_email: string | null
  triggered_by_name: string | null
  details: Record<string, unknown> | null
}

export interface Lead {
  id: string
  company_name: string
  contact_name: string
  contact_email: string
  contact_phone: string | null
  industry: string | null
  location: string | null
  source: string
  status: string
  notes: string | null
  created_at: string
  updated_at: string | null
  follow_up_date: string | null
  last_contacted: string | null
  source_ref: string | null
  assigned_to: string | null
  assigned_to_name: string | null
  assigned_to_email: string | null
}

export interface AuthState {
  access_token: string | null
  user: { user_id: string; email: string; name: string; role: string } | null
  isAuthenticated: boolean
}
