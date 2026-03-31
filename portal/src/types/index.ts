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
  current_status?: string
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
  task_ref: string | null
  content: string | null
  status: string
  department: string | null
  progress: number | null
  current_step: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
  error: string | null
  triggered_by_email: string | null
  triggered_by_name: string | null
  details: Record<string, unknown> | null
  total_tokens?: number
  input_tokens?: number
  output_tokens?: number
  llm_model?: string | null
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
  lead_type?: string
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

export interface TaskStats {
  all: number
  queued: number
  running: number
  completed: number
  failed: number
  cancelled: number
}

export interface ActiveTask {
  id: string
  task_id?: string
  status: string
  result?: {
    response?: string
    reply?: string
    [key: string]: unknown
  } | string | null
  session_id?: string
  department?: string | null
  created_at?: string
  completed_at?: string | null
  error?: string | null
}

export interface Plan {
  plan_id: string
  goal: string
  status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED'
  steps_total: number
  steps_completed: number
  agents: string[]
  created_at: string
  completed_at?: string
  duration_ms?: number
  total_tokens?: number
  input_tokens?: number
  output_tokens?: number
  llm_model?: string | null
}

export interface PlanStep {
  step_id: string
  step_number: number
  agent_id: string
  description: string
  status: string
  quality_score?: number
  summary?: string
  issues?: string[]
  review?: Record<string, unknown>
  retry_count: number
  started_at?: string
  completed_at?: string
  instructions?: string
  output?: Record<string, unknown>
}

export interface PlanDetail extends Plan {
  steps: PlanStep[]
  shared_context?: Record<string, unknown>
  final_output?: string
  goal_summary?: string
  execution_mode?: string
}

export interface HREmployee {
  id: string
  user_id: string | null
  staff_id: string
  full_name: string
  email: string
  phone: string | null
  department: string
  job_title: string | null
  employment_type: 'full_time' | 'part_time' | 'contract'
  country: string
  location_office: string | null
  manager_id: string | null
  manager_name?: string | null
  annual_leave_days: number
  sick_leave_days: number
  other_leave_days: number
  hire_date: string
  probation_end_date: string | null
  is_active: boolean
  profile_notes: string | null
  created_at: string
  updated_at: string
}

export interface HRLeaveType {
  id: string
  name: string
  code: string
  is_paid: boolean
  requires_document: boolean
  country: string | null
  is_active: boolean
}

export interface HRLeaveApplication {
  id: string
  employee_id: string
  employee_name?: string
  leave_type_id: string
  leave_type_name?: string
  start_date: string
  end_date: string
  total_days: number
  half_day: boolean
  half_day_period: string | null
  reason: string | null
  status: 'pending' | 'approved' | 'rejected' | 'cancelled'
  approver_id: string | null
  approver_name?: string | null
  approver_comment: string | null
  applied_via: string
  created_at: string
  updated_at: string
}

export interface HRLeaveBalance {
  id: string
  employee_id: string
  leave_type_id: string
  leave_type_name?: string
  leave_type_code?: string
  year: number
  entitled_days: number
  carried_over: number
  taken_days: number
  pending_days: number
  remaining_days: number
}

export interface HRLeaveDashboard {
  total_active_employees: number
  on_leave_today: number
  pending_approvals: number
  leaves_this_month: number
  employee_summaries: Array<{
    employee_id: string
    staff_id: string
    full_name: string
    department: string
    country: string
    leave_balances: HRLeaveBalance[]
    pending_applications: number
    last_updated: string
  }>
}

// ─── Finance Module Types ─────────────────────────────────────────────────

export interface FinEntity {
  id: string
  code: string
  name: string
  entity_type: 'subsidiary' | 'holding' | 'branch' | 'group'
  country_code?: string
  base_currency: string
  parent_entity_id?: string
  tax_id?: string
  business_id?: string
  is_active: boolean
  created_at: string
}

export interface FinAccount {
  id: string
  entity_id: string
  category_id: string
  code: string
  name: string
  description?: string
  currency: string
  account_type: string
  is_bank_account: boolean
  is_control: boolean
  is_active: boolean
}

export interface JournalLine {
  id?: string
  account_id: string
  description?: string
  debit_amount: number
  credit_amount: number
  currency?: string
  tax_code?: string
  line_order?: number
}

export interface JournalEntry {
  id: string
  entity_id: string
  period_id?: string
  entry_number: string
  entry_date: string
  description: string
  reference?: string
  currency: string
  exchange_rate: number
  status: 'draft' | 'posted' | 'reversed'
  created_at: string
  lines?: JournalLine[]
}

export interface LineItem {
  description: string
  quantity: number
  unit_price: number
  tax_rate?: number
  amount?: number
}

export interface FinCustomer {
  id: string
  entity_id: string
  customer_code: string
  name: string
  company_name?: string
  email?: string
  phone?: string
  currency: string
  payment_terms: number
  is_active: boolean
  created_at: string
  industry?: string
  location?: string
  account_manager?: string
  customer_type?: string
}

export interface FinVendor {
  id: string
  entity_id: string
  vendor_code: string
  name: string
  company_name?: string
  email?: string
  currency: string
  payment_terms: number
  is_active: boolean
  created_at: string
}

export interface FinInvoice {
  id: string
  entity_id: string
  invoice_number: string
  customer_id: string
  customer_name?: string
  invoice_date: string
  due_date: string
  currency: string
  subtotal: number
  tax_amount: number
  total_amount: number
  paid_amount: number
  outstanding: number
  status: 'draft' | 'sent' | 'partial' | 'paid' | 'overdue' | 'cancelled' | 'void'
  line_items: LineItem[]
  created_at: string
}

export interface FinQuote {
  id: string
  entity_id: string
  quote_number: string
  customer_id: string
  customer_name?: string
  quote_date: string
  expiry_date?: string
  currency: string
  subtotal: number
  tax_amount: number
  total_amount: number
  status: 'draft' | 'sent' | 'accepted' | 'declined' | 'expired' | 'converted'
  created_at: string
}

export interface FinBill {
  id: string
  entity_id: string
  bill_number: string
  vendor_id: string
  vendor_name?: string
  bill_date: string
  due_date: string
  currency: string
  total_amount: number
  paid_amount: number
  outstanding: number
  status: 'pending' | 'approved' | 'partial' | 'paid' | 'cancelled'
  created_at: string
}

export interface FinPayment {
  id: string
  entity_id: string
  payment_number: string
  payment_type: 'receipt' | 'payment'
  payment_date: string
  currency: string
  amount: number
  payment_method?: string
  reference?: string
  created_at: string
}

export interface FinExpense {
  id: string
  entity_id: string
  expense_number: string
  expense_date: string
  category: string
  description: string
  currency: string
  amount: number
  tax_amount: number
  status: 'pending' | 'approved' | 'rejected' | 'reimbursed'
  created_at: string
}

export interface FinBankAccount {
  id: string
  entity_id: string
  bank_name: string
  account_name: string
  account_number?: string
  currency: string
  current_balance: number
  last_reconciled?: string
  is_active: boolean
}

export interface FinShareholder {
  id: string
  entity_id: string
  name: string
  shareholder_type: 'individual' | 'company'
  share_class: string
  shares_held: number
  ownership_pct?: number
  effective_date: string
  is_active: boolean
}

export interface FinPeriod {
  id: string
  entity_id: string
  name: string
  period_type: 'monthly' | 'quarterly' | 'annual'
  start_date: string
  end_date: string
  status: 'open' | 'closed' | 'locked'
}

export interface FinTaxCode {
  id: string
  entity_id: string
  code: string
  name: string
  tax_type: string
  rate: number
  applies_to: string
  is_active: boolean
}

export interface FinanceDashboardData {
  kpis: {
    ar_outstanding: number
    ap_outstanding: number
    cash_balance: number
  }
  pnl_mtd: {
    total_income: number
    total_expenses: number
    net_profit: number
  }
  ar_aging: {
    buckets: Record<string, any[]>
    total_outstanding: number
  }
  recent_journal_entries: JournalEntry[]
}
